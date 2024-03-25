import serial
import sys
import binascii
from time import sleep
import numpy as np
ser = serial.Serial()
ser.baudrate = 19200
ser.parity=serial.PARITY_SPACE
ser.stopbits=serial.STOPBITS_TWO
ser.timeout=3
STX = 0x02
ETX = 0x03

global common_delay
common_delay = 0.3

#common messages for all displays

VALID_COMMANDS = {"Clear": [0x30, 0x30, 0x30, 0x32, 0x30, 0x42],
                  "Selftest": [0x30, 0x30, 0x30, 0x34, 0x31, 0x46, 0x30, 0x31],
                  "Pictest": [0x30, 0x30, 0x30, 0x34, 0x31, 0x46, 0x30, 0x32],
                  "image_start": [0x30, 0x30, 0x30, 0x32, 0x30, 0x43],
                  "image_end": [0x30, 0x30, 0x30, 0x32, 0x31, 0x34]
}


def open_port(port):        #opens the selected serial port. input paramter example: "COM3"

    try:
        ser.port = port
        ser.open()
    except serial.serialutil.SerialException:
        raise ConnectionRefusedError 

def serial_ports():         #returns a list containing all available serial ports. stolen from stackoverflow. THANKS!
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

def req_ack(address):       #sends and ACK request to the given display and displays the response wich should be 0306 if the display is available
    global STX, ETX
    display_address = list(convert_address(address))  #convert to protocol address from physical address
    display_address[1] = display_address[1]+1
    result = [0x02, display_address[0], display_address[1], 0x03]   #add framing
    
    for i in result:
        ser.write(bytes(i)) #convert to bytes and write to serial port
        print(hex(i))


    byte = ser.read()  #read 4 bites of the response data
    print(byte)
    
    

def byte_split(hex_string): #converts the inputs string of a hexadecimal value to the two ASCII values representing the characters of the input string. param: one string of characters representing a hex value
    # Remove the '0x' prefix if it exists
    if hex_string.startswith('0x'):
        hex_string = hex_string[2:]

    hex_string = hex_string.upper()

    # Convert hexadecimal string to integer
    decimal_value = int(hex_string, 16)

    # Convert decimal value to ASCII characters
    ascii_values = tuple(ord(char) for char in hex_string)      #i have a SLIGHT feeling this function could be optimised

    return ascii_values

def convert_address(display_address):   #takes a decimal integer as input and calculates the display's address bytes as described by the protocoll
    display_address = hex((display_address+32)*4).upper()
    display_address = (ord(display_address[-2])), ord(display_address[-1])
    
    return display_address

def bin_to_ascii(arr):      #takes an 8 bit long binary number (ex: 0b01011000) and coverts it to two ASCII values of the top and bottom 4 bits.
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
    
def calculate_checksum(values):      #calculates the checksum bytes of the input wich must be a list containing hex or dec values. the input must already contain the STX byte, but not the EXT.
    #print(values)
    try:
        if len(values) < 2:
            raise ValueError("The input list must contain at least two decimal values.")
        
        # Add all values except the first one. this is where we skip the STX byte.
        chksum = sum(values[1:])
        
        
        # Subtract 256 from the sum.
        chksum_result = chksum - 256
        
        # Ensure the result is within the range of 0-255,.
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

def send(cmd_bytes, address=31):    #one of the most important functions. param: cmd_bytes: a list of hexa values containing the command desired to be sent, for example from the VALID_COMMANDS list

    #calculate display address according to protocol            
    disp_addr= convert_address(address)

    #add header (STX, address)
    result = [2]
    for i in disp_addr:
        result.append(i)

    #add content bytes
    for i in cmd_bytes:
        result.append(i)
        
    #add footer (Checksum, ETX)
    crc = calculate_checksum(result)
    result.append(crc[0])
    result.append(crc[1])
    result.append(3)    #ETX
    
    hex_values = [hex(value)[2:].zfill(2) for value in result] #removes the "0x" from every hexa bytes


    # Send the hexadecimal values as bytes to the serial port. FINALLY we are sending something
    for hex_value in hex_values:
        ser.write(bytes.fromhex(hex_value))
        #print(f"Sent: 0x{hex_value}")
        ()

def process_image(image_array):                 #this is where it gets nasty. Takes an 2D array as input wich must be 1:1 the size of the display
    block_number = 1                            #then it decides if the display is so large, that the display data must be split into blocks.
    block_list = list()                         #it currently contains untested parts as I dont have displays on hand for all 4 cases
    hex_image_array = list()

    display_width = len(image_array)            #the 2D array's top array must be the width of the display
    display_height = len(image_array[0])        #we take the 1st sub array's length as the height. As all columns must be the same height this must be no problem

    #check if it is necessary to split into blocks:
    
    #managing blocks
    """
    1) display height under 8 pixels, and width less than or equal to 96 pixels
    2) display height taller than 8 pixels, and width less than or equal to 96
    3) display height less than 8 pixels,but wider than 96 pixels ( a VERY rare CASE)
    4) dispaly height taller than 8 pixels and wider than 96 pixels"""

    # ------------------------- CASE 1 ------------------------- TESTED OK
    if display_height <= 8 and display_width <= 96:
        print("case 1")
        if display_height == 7:
            extra_column  = np.zeros((display_width,1))
            image_array = np.hstack((extra_column, image_array))              #7 pixel tall displays appear as 8 pixels tall accroding to the protocol, and the last, "phantom" pixel is always 0
    
        block_length = byte_split(hex(display_width*2))
        
        image_array_block_1 = [48,49]       #block IDs
        for i in block_length:
            image_array_block_1.append(i)   #block lengths
                               
        for column in image_array:           #convert from binary data to hex values
            tmp = bin_to_ascii(column)
            image_array_block_1.append(tmp[0])
            image_array_block_1.append(tmp[1])
            
        block_list.append(image_array_block_1)
        

        
    # ------------------------- CASE 2 ------------------------- TESTED OK
    elif display_height > 8 and display_width <= 96:
        print("case 2")
        block_number = 2
        block_length = byte_split(hex(display_width*2))
        
        image_array_block_1 = [0x30,0x31]           #block IDs
        image_array_block_2 = [0x30,0x32]

        for i in block_length:                      #block lengths. In this cases both block are equal lengths
            image_array_block_1.append(i)
            image_array_block_2.append(i)
        

        for column in image_array:
            
            tmp = bin_to_ascii(column[8:])          #convert from binary data to hex values
            image_array_block_1.append(tmp[0])      #upper (1st) block
            image_array_block_1.append(tmp[1])
            
            tmp = bin_to_ascii(column[:8])
            image_array_block_2.append(tmp[0])      #blower (2nd) block
            image_array_block_2.append(tmp[1])      

        block_list.append(image_array_block_1)
        block_list.append(image_array_block_2)
            
    # ------------------------ CASE 3 -------------------------- #untested, but very rare case
    elif display_height <= 8 and display_width > 96:
        print("case 3")
        block_number = 2

            
        image_array_block_1 = [0x30,0x31]           #block IDs
        image_array_block_2 = [0x30,0x32]

        block_length = byte_split(hex(96/2))
        for i in block_length:
            image_array_block_1.append(i)

        block_length = byte_split(hex((display_width-96)/2))
        for i in block_length:
            image_array_block_2.append(i)
 
        
        for column in image_array[:96]:           #first 69 columns convert to hex
            tmp = bin_to_ascii(column)
            image_array_block_1.append(tmp[0])
            image_array_block_1.append(tmp[1])
            
        for column in image_array[96:]:           #all columns after 96 convert to hex
            tmp = bin_to_ascii(column)
            image_array_block_2.append(tmp[0])
            image_array_block_2.append(tmp[1])

        block_list.append(image_array_block_1)
        block_list.append(image_array_block_2)

    # ------------------------ CASE 4 -------------------------- #untested but more common case 
    elif display_height > 8 and display_width > 96:
        block_number = 4
        print("case 4")
        
        block_length = byte_split(hex(96*2))
        block2_length = byte_split(hex((display_width - 96)*2))
        
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

            tmp = bin_to_ascii(column[:8])          #convert from binary data to hex values
            image_array_block_1.append(tmp[0])      #top
            image_array_block_1.append(tmp[1])

            tmp = bin_to_ascii(column[8:])          #convert from binary data to hex values
            image_array_block_3.append(tmp[0])      #top
            image_array_block_3.append(tmp[1])
            

        for column in tmp_array2:
            tmp = bin_to_ascii(column[:8])          #convert from binary data to hex values
            image_array_block_2.append(tmp[0])      #top
            image_array_block_2.append(tmp[1])

            tmp = bin_to_ascii(column[8:])          #convert from binary data to hex values
            image_array_block_4.append(tmp[0])      #top
            image_array_block_4.append(tmp[1])

        del tmp_array1, tmp_array2

        block_list.append(image_array_block_1)
        block_list.append(image_array_block_2)
        block_list.append(image_array_block_3)
        block_list.append(image_array_block_4)

    return block_list


def send_image(image_array, address, protocol):     #use this image to handle sendling images.
                                                    #params:
                                                    #   -image array: 2D array of the image data. must be 1:1 the size of the display. each value must be a hexadecimal value.
                                                    #               where the binary bit of the value is 1, the pixel on that postion will be flipped to the bright side.
                                                    #   -address must be the pyhiscal address of the display
                                                    # protocol can be 1 or 2, each is different. depends on the display you use.
    if protocol == 1:
        processed_image = process_image(image_array)    #this is the simple version, no pre-processing needed
        
    elif protocol == 2:                                 #in this more complicated version the first 32 columns are sent last. The first column sent it #33.
        new_image_array = list()
        for i in image_array[32:]:
            new_image_array.append(i)
        for i in image_array[:32]:
            new_image_array.append(i)
            
        processed_image = process_image(new_image_array)
        
    converted_address = convert_address(address)        #for all image transmissions the beginning of the image data must be preceeded by the image start command from the valid commands list.
    global common_delay

    send(VALID_COMMANDS["image_start"])
    sleep(common_delay)
    
    for block in processed_image:                   #finalizing: adding STX, address, checksum
        block.insert(0, 2)                          #this could be optimized I know
        block.insert(1, converted_address[0])
        block.insert(2, converted_address[1])
        checksum = calculate_checksum(block)
        block.append(checksum[0])
        block.append(checksum[1])
        block.append(3)
        byteliterals=bytes(block)
        ser.write(byteliterals)
        sleep(common_delay)
    send(VALID_COMMANDS["image_end"])
5    
    
    
# ____________________--------- EXAMPLES ---------- _____________________        
        
ports = serial_ports()
print(ports)
open_port(ports[0])     #change this to your desired port
#open_port("COM2")      this also works

print("clearing all displays")
send(VALID_COMMANDS["Clear"])       #clear all displays
sleep(1)                            #do not send commands with short interval
print("self test in display #4")
send(VALID_COMMANDS["Selftest"], 4) # starts self test on display address 4, note that the display will continue to do the selftest until it recieves another command
sleep(5)



#sending images: (for a 96x7 sized display, modify the example_image_array for different display sizes)

example_image_array = ([255, 255, 255, 255, 255, 255, 255],
 [  0,   0,   0, 255,   0,   0, 255],
 [  0,   0,   0, 255,   0,   0, 255],
 [  0,   0,   0,   0,   0,   0, 255],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0, 255, 255, 255, 255, 255,   0],
 [255,   0,   0,   0,   0,   0, 255],
 [255,   0,   0,   0,   0,   0, 255],
 [  0, 255, 255, 255, 255, 255,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [255, 255, 255, 255, 255, 255, 255],
 [  0,   0,   0, 255,   0,   0,   0],
 [  0,   0, 255,   0, 255,   0,   0],
 [255, 255,   0,   0,   0, 255, 255],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0, 255,   0,   0,   0,   0],
 [  0,   0, 255,   0,   0,   0,   0],
 [  0,   0, 255,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0, 255, 255, 255, 255, 255,   0],
 [255,   0,   0,   0,   0,   0, 255],
 [255,   0,   0, 255,   0,   0, 255],
 [  0, 255, 255, 255,   0, 255,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0, 255, 255, 255, 255],
 [255, 255, 255, 255,   0,   0,   0],
 [  0,   0,   0, 255, 255, 255, 255],
 [  0,   0,   0,   0,   0,   0,   0],
 [255, 255, 255, 255, 255, 255, 255],
 [255,   0,   0, 255,   0,   0, 255],
 [255,   0,   0, 255,   0,   0, 255],
 [255,   0,   0,   0,   0,   0, 255],
 [  0,   0,   0,   0,   0,   0,   0],
 [255, 255, 255, 255, 255, 255, 255],
 [  0,   0,   0,   0,   0, 255,   0],
 [  0,   0,   0,   0, 255,   0,   0],
 [  0,   0,   0,   0,   0, 255,   0],
 [255, 255, 255, 255, 255, 255, 255],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0, 255],
 [255, 255, 255, 255,   0,   0, 255],
 [  0,   0,   0,   0, 255,   0, 255],
 [  0,   0,   0,   0,   0, 255, 255],
 [  0,   0,   0,   0,   0,   0,   0],
 [255, 255,   0,   0,   0, 255, 255],
 [  0,   0, 255,   0, 255,   0,   0],
 [  0,   0,   0, 255,   0,   0,   0],
 [  0,   0, 255,   0, 255,   0,   0],
 [255, 255,   0,   0,   0, 255, 255],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0, 255,   0,   0, 255, 255,   0],
 [255,   0,   0, 255,   0,   0, 255],
 [255,   0,   0, 255,   0,   0, 255],
 [  0, 255, 255, 255, 255, 255,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0, 255, 255, 255, 255, 255,   0],
 [255,   0,   0, 255,   0,   0, 255],
 [255,   0,   0, 255,   0,   0, 255],
 [  0, 255, 255,   0,   0, 255,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0],
 [  0,   0,   0,   0,   0,   0,   0])
#send image command,

print("sending image to display #4, protocol type 1")
send_image(example_image_array, 4, 1)   #send the example image array to display address 4, with protocol type 1



    
