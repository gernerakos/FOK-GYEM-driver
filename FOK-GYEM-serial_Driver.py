import serial
import sys
from time import sleep
import numpy as np
ser = serial.Serial()

ser.timeout=3
STX = 2
ETX = 0x03

global VMX_STX, VMX_ETX
VMX_STX = 0x78
VMX_ETX = 0

display_address = 31

global common_delay
common_delay = 0.3

global current_protocol 
current_protocol = None

#common messages

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


##Clear = ()
##Selftest = ()
##Selftest: [0x30, 0x30, 0x30, 0x34, 0x31, 0x46, 0x30, 0x31]
##Pictest: [0x30, 0x30, 0x30, 0x34, 0x31, 0x46, 0x30, 0x32]


#02 91 03

FGY_VALID_COMMANDS = {"Clear": [0x30, 0x30, 0x30, 0x32, 0x30, 0x42],
                  "Selftest": [0x30, 0x30, 0x30, 0x34, 0x31, 0x46, 0x30, 0x31],
                  "Pictest": [0x30, 0x30, 0x30, 0x34, 0x31, 0x46, 0x30, 0x32],
                  "image_start": [0x30, 0x30, 0x30, 0x32, 0x30, 0x43],
                  "image_end": [0x30, 0x30, 0x30, 0x32, 0x31, 0x34]
}

VMX_VALID_COMMANDS = {"Clear": [0x00, 0x10, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x06, 0x00, 0x00, 0x00, 0x00, 0x00],
                  "Selftest": [0x00, 0x10, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x06, 0x02, 0x00, 0x00, 0x00, 0x00],
                  "Clear memory": [0x00, 0x10, 0x0B, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x06, 0xFF, 0x00, 0x00, 0x00, 0x00],
                  "image_start": [0x00, 0x10, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46, 0x01, 0x00, 0x00, 0x00, 0x00],
                  "image_end": [0x00, 0x10, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x06, 0x01, 0x00, 0x00, 0x00, 0x00], 
                  "ack_req": [0x00, 0x10, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x06, 0x00, 0x00, 0x00, 0x00, 0x00], 
}
#all messages start with STX
#followed by the display address, after adding 32 to it, and multiplying the result with 4.
#the resulted hexadecimal value's each character's corresponding ASCII value is sent to the display
#this is followed by the message itself, more on this later
#each message closes with the CRC bytes, wich is calculated as following:
#the CRC adds all values before the CRC bytes, except for the first byte (STX byte)
#this sum of values is then decreased by 256.
#as in the display address, the resulted CRC value's each character's corresponding ASCII values are added to
#the end of the message. This is usually two bytes.
#the message is closed with the ETX wich is not part of the CRC.

#final message is as follows (value[length])
#STX[1], address[1], address[2], message[varying], CRC[1], CRC[2], ETX

#step 1:
#   calculate display address
#step 2:
#   add address to message
#step 3:
#   calculate CRC
#step 4:
#    add STX and EXT bytes
#step 5:
#    send data on serial

def open_port(port):

    try:
        ser.port = port
        ser.open()
    except serial.serialutil.SerialException:
        raise ConnectionRefusedError 
    else:
        print("[SERIAL DRIVER]: serial port opened on", port)

def close_port(port):

    try:
        ser.port = port
        ser.close()
    except serial.serialutil.SerialException:
        raise ConnectionRefusedError 
    else:
        print("[SERIAL DRIVER]: serial port closed on", port)

def serial_ports():
    """ Lists serial port names

        :raises EnvironmentError:
            On unsupported or unknown platforms
        :returns:
            A list of the serial ports available on the system
    """
    if sys.platform.startswith('win'):
        ports = ['COM%s' % (i + 1) for i in range(256)]
    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        # this excludes your current terminal "/dev/tty"
        ports = glob.glob('/dev/tty[A-Za-z]*')
    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.*')
    else:
        raise EnvironmentError('Unsupported platform')

    result = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    return result

def custom_readline(ser, eol=b'\n'):
    """
    Reads from the serial port until the specified end-of-line character is found.
    
    :param ser: The serial port object.
    :param eol: The end-of-line character to look for. Default is newline (`\n`).
    :return: The read line as a bytes object.
    """
    line = bytearray()

    timeout = 0

    while True:
        timeout += 1
        char = ser.read(1)
        line += char
        if char == eol:
            break

        if timeout == 1000:
            print("[SERIAL DRIVER] FGY ACK timeout error")
            return b''


    hex_array = [format(byte, '02x') for byte in line]
    return hex_array

def FGY_req_ack(address):
    global STX, ETX

    protocol_manager(" FOK-GYEM (bkv)")

    conv_address = FGY_convert_address(address)

    result = ['0x02', hex(conv_address[0]), hex(conv_address[1]+1), '0x03']

    data_to_send = bytes([int(value, 16) for value in result])

    ser.write(data_to_send)
    # Read a single line using the custom EOL character
    resp = ser.read(2)

    if resp == b'' or []:
        print("[SERIAL DRIVER] FGY ACK Response from {}: ".format(address), "NG")
        return "NG"
    else:
        print("[SERIAL DRIVER] FGY ACK Response from {}: ".format(address), "OK")
        return "OK"

def FGY_byte_split(hex_string): #param: one string of characters representing a hex value
    # Remove the '0x' prefix if it exists
    if hex_string.startswith('0x'):
        hex_string = hex_string[2:]

    hex_string = hex_string.upper()

    # Convert hexadecimal string to integer
    decimal_value = int(hex_string, 16)

    # Convert decimal value to ASCII characters
    ascii_values = tuple(ord(char) for char in hex_string)

    return ascii_values

def FGY_convert_address(display_address):   #takes a decimal integer as input and calculates the display's address bytes as described by the protocoll
    display_address = hex((display_address+32)*4).upper()
    display_address = (ord(display_address[-2])), ord(display_address[-1])
    
    return display_address

def FGY_bin_to_ascii(arr):
        # Check if the array has at least 4 elements
        if len(arr) < 4:
            return None, None  # Not enough values in the array

        binary_string = ''.join(['1' if val else '0' for val in arr])

        # Convert the first 4 binary values to a binary string
        first_four_binary = ''.join(map(str, binary_string[:4]))
        last_four_binary = ''.join(map(str, binary_string[4:]))

        # Calculate ASCII values of the hexadecimal characters
        first_hex = hex(int(first_four_binary, base=2))[2].upper()
        last_hex = hex(int(last_four_binary, base=2))[2].upper()

        first_result = ord(first_hex)
        last_result = ord(last_hex)

        return first_result, last_result
    
def FGY_calculate_checksum(values):      #calculates the CRC bytes of the input wich must be a list containing hex or dec values
    #print(values)
    try:
        if len(values) < 2:
            raise ValueError("The input list must contain at least two decimal values.")
        
        # Add all values except the first one.
        chksum = sum(values[1:])
        
        
        # Subtract 256 from the sum.
        chksum_result = chksum - 256
        
        # Ensure the result is within the range of 0-255.
        #crc_result = crc_result % 256
        
        # Split the last two digits into separate digits

        hex_chksum = hex(chksum_result)
        #print(hex(ord(hex_crc[-2].upper())))

        chksum_digit1 = ord(hex_chksum[-2].upper())
        chksum_digit2 = ord(hex_chksum[-1].upper())
        
        #print(hex_crc,crc_result)
        
        return chksum_digit1, chksum_digit2
    except ValueError as e:
        return str(e)

def FGY_send_command(cmd_bytes, address=31):

    #calculate display address according to protocol            
    disp_addr= FGY_convert_address(address)

    #add header (STX, address)
    result = [2]
    for i in disp_addr:
        result.append(i)

    #add content bytes
    for i in cmd_bytes:
        result.append(i)
        
    #add footer (Checksum, ETX)
    crc = FGY_calculate_checksum(result)
    result.append(crc[0])
    result.append(crc[1])
    result.append(3)
    
    hex_values = [hex(value)[2:].zfill(2) for value in result]

    # FGY_send_command the hexadecimal values as bytes to the serial port.
    for hex_value in hex_values:
        ser.write(bytes.fromhex(hex_value))
        #print(f"Sent: 0x{hex_value}")
        ()

def FGY_process_image(image_array):
    #print("passed on as:\n",image_array)
    block_list = list()

    display_width = len(image_array)
    display_height = len(image_array[0])

    

    #check if it is necessary to split into blocks:
    
    #managing blocks
    """
    1) display height under 8 pixels, and width less than 100 pixels
    2) display height equal to or under 16 pixels, width equal to or under 32 pixels
    3) display height taller than 8 pixels, and width less than 100
    4) display height less than 8 pixels,but wider than 100 pixels
    5) dispaly height taller than 8 pixels and wider than 100 pixels"""

    # ------------------------- CASE 1 ------------------------- 
    if display_height <= 8 and display_width <= 96:
        if display_height == 7:
            extra_column  = np.zeros((display_width,1))
            image_array = np.hstack((extra_column, image_array))              #7 pixel tall displays appear as 8 pixels tall accroding to the protocol, and the last, "phantom" pixel is always 0
    
        block_length = FGY_byte_split(hex(display_width*2))
        
        image_array_block_1 = [48,49]
        for i in block_length:
            image_array_block_1.append(i)
                               
        for column in image_array:           #convert from binary data to hex values
            tmp = FGY_bin_to_ascii(column)
            image_array_block_1.append(tmp[0])
            image_array_block_1.append(tmp[1])
            
        block_list.append(image_array_block_1)

    # ------------------------- CASE 2 -------------------------            displays smaller than or equal to 16x32


    elif display_height <= 16 and display_width <=32:

        if display_height == 14 and display_width == 28:
            image_array = np.pad(image_array, pad_width=((1, 1), (1, 1)), mode='constant', constant_values=0)
            image_array = np.pad(image_array, pad_width=((1, 1), (0, 0)), mode='constant', constant_values=0)

        block_length = FGY_byte_split(hex(128))
        image_array_block_1 = [0x30,0x31]

        for i in block_length:
            image_array_block_1.append(i)

        for column in image_array:

            top = FGY_bin_to_ascii(column[8:]) #TOP          #convert from binary data to hex values

            image_array_block_1.append(top[0])
            image_array_block_1.append(top[1])


        for column in image_array:

            btm = FGY_bin_to_ascii(column[:8]) #bottom

            image_array_block_1.append(btm[0])
            image_array_block_1.append(btm[1])


        block_list.append(image_array_block_1)
        

        
    # ------------------------- CASE 3 -------------------------            DISPLAYS smaller than or equal to 8 pixels, but smaller than or equal to 96px
    elif display_height > 8 and display_width <= 96:
        block_length = FGY_byte_split(hex(display_width*2))
        
        image_array_block_1 = [0x30,0x31]
        image_array_block_2 = [0x30,0x32]

        for i in block_length:
            image_array_block_1.append(i)
            image_array_block_2.append(i)
        

        for column in image_array:
            
            tmp = FGY_bin_to_ascii(column[8:])          #convert from binary data to hex values
            image_array_block_1.append(tmp[0])      #top
            image_array_block_1.append(tmp[1])
            
            tmp = FGY_bin_to_ascii(column[:8])
            image_array_block_2.append(tmp[0])      #bottom
            image_array_block_2.append(tmp[1])      

        block_list.append(image_array_block_1)
        block_list.append(image_array_block_2)
            
    # ------------------------ CASE 5 --------------------------            DISPLAYS smaller than or equal to 8 pixels, but wider than 96px
    elif display_height <= 8 and display_width > 96:
        
        image_array_block_1 = [0x30,0x31]   
        image_array_block_2 = [0x30,0x32]

        block_length = FGY_byte_split(hex(display_width/2))
        for i in block_length:
            image_array_block_1.append(i)
            image_array_block_2.append(i)
 
        
        for column in image_array[:96]:           #first 100 pixels convert to hex
            tmp = FGY_bin_to_ascii(column)
            image_array_block_1.append(tmp[0])
            image_array_block_1.append(tmp[1])
            
        for column in image_array[96:]:           #all pixels after 100 convert to hex
            tmp = FGY_bin_to_ascii(column)
            image_array_block_2.append(tmp[0])
            image_array_block_2.append(tmp[1])

        block_list.append(image_array_block_1)
        block_list.append(image_array_block_2)

    # ------------------------ CASE 4 --------------------------
    elif display_height > 8 and display_width > 96:
        
        block_length = FGY_byte_split(hex(96*2))
        block2_length = FGY_byte_split(hex((display_width - 96)*2))
        
        image_array_block_1 = [0x30,0x31]
        image_array_block_2 = [0x30,0x32]
        image_array_block_3 = [0x30,0x33]
        image_array_block_4 = [0x30,0x34]

        for i in block_length:
            image_array_block_1.append(i)
            image_array_block_3.append(i)
        for i in block2_length:
            image_array_block_2.append(i)
            image_array_block_4.append(i)
            
    
        tmp_array1 = image_array[:96]
        tmp_array2 = image_array[96:]

        for column in tmp_array1:

            tmp = FGY_bin_to_ascii(column[8:])          #convert from binary data to hex values
            image_array_block_1.append(tmp[0])      #top
            image_array_block_1.append(tmp[1])

            tmp = FGY_bin_to_ascii(column[:8])          #convert from binary data to hex values
            image_array_block_3.append(tmp[0])      #top
            image_array_block_3.append(tmp[1])
            

        for column in tmp_array2:
            tmp = FGY_bin_to_ascii(column[8:])          #convert from binary data to hex values
            image_array_block_2.append(tmp[0])      #top
            image_array_block_2.append(tmp[1])

            tmp = FGY_bin_to_ascii(column[:8])          #convert from binary data to hex values
            image_array_block_4.append(tmp[0])      #top
            image_array_block_4.append(tmp[1])

        del tmp_array1, tmp_array2

        block_list.append(image_array_block_1)
        block_list.append(image_array_block_2)
        block_list.append(image_array_block_3)
        block_list.append(image_array_block_4)

    return block_list





# ================================== >>> COMMON FUNCTIONS <<< =====================================

def send_image(image_array, address, protocol):

    protocol_manager(protocol)

    if protocol == " FOK-GYEM (bkv)":
        processed_image = FGY_process_image(image_array)
        
    elif protocol == " Mobilinform (Volán)":
        new_image_array = list()
        for i in image_array[32:]:
            new_image_array.append(i)
        for i in image_array[:32]:
            new_image_array.append(i)
            
        processed_image = FGY_process_image(new_image_array)

    if protocol == " FOK-GYEM (bkv)" or protocol == " Mobilinform (Volán)":
 
        converted_address = FGY_convert_address(address)
        global common_delay

        FGY_send_command(FGY_VALID_COMMANDS["image_start"], address)
        sleep(common_delay)
    
        for block in processed_image:                   #finalizing: adding STX, address, checksum
            block.insert(0, 2)
            block.insert(1, converted_address[0])
            block.insert(2, converted_address[1])
            checksum = FGY_calculate_checksum(block)
            block.append(checksum[0])
            block.append(checksum[1])
            block.append(3)
            byteliterals=bytes(block)
            ser.write(byteliterals)
            sleep(common_delay)
        FGY_send_command(FGY_VALID_COMMANDS["image_end"], address)
        resp = FGY_req_ack(address)

    return resp
        

def send_command(command, address, protocol):
    protocol_manager(protocol)

    if protocol == " FOK-GYEM (bkv)" or protocol == " Mobilinform (Volán)":
        cmd_bytes = FGY_VALID_COMMANDS[command]
        FGY_send_command(cmd_bytes, address)
        #print("[SERIAL DRIVER]: FOK PROTOCOL", command)

def protocol_manager(protocol):
    global current_protocol

    if current_protocol != protocol:
        if protocol == " FOK-GYEM (bkv)" or protocol == " Mobilinform (Volán)":
            ser.baudrate = 19200
            ser.parity=serial.PARITY_SPACE
            ser.stopbits=serial.STOPBITS_TWO 
            ser.timeout = 0.3
            print("[SERIAL DRIVER]: //Protocol manager// serial mode changed to FGY")
            
        current_protocol = protocol

         
#open_port("COM8")
#protocol_manager(" FOK-GYEM (bkv)")
#while 1:
#    resp = ser.readlines()

#    if resp != []:
#        print(resp)




#FGY_send_command(VALID_COMMANDS["Clear"])


'''sending images:


read image array as:
make two arrays for the two blocks (top 8 rows and bottom 8 rows)
    array_top and array_bottom
    each array should start with the block ID (1 and 2, split into to bytes using the FGY_byte_split() function)
    then it should contain the block length (display_width * 2, split into to bytes using the FGY_byte_split() function)

    then
    
read every column starting from 0
    split each column as:
    first 8 values goes into array_bottom
    last 8 values goes into array_top

add header to each array:
    STX, display address
    CRC, ETX

send header + 30 30 30 32 30 43 + footer [= start image transmission // ---- send(VALID_COMMANDS["image_start"])]
send image array_top
send image array_bottom
send header + 30 30 30 32 31 34 + footer [= end image transmission  -------- send(VALID_COMMANDS["image_end"])]'''

    
