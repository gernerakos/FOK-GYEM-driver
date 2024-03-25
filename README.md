A short and not optimized serial driver file for the FOK-GYEM flipdot displays, wich were made in hungary and were used on public transport vehicles including buses, trams and metros.

There are examples at the end of the file to make it easier to use.
There are a few untested parts for larger displays, as I have no such large displays on hand.
Because of this I take no repsonibility for the reliable operation of this code, or in any damage of the display due to untested code

The basic commands can be called usind the send(VALID_COMMANDS["Clear"]) method, where the "Clear" can be replaced to any of the keys in the VALID_COMMANDS dictionary
To send custom image data, a 2D array is necessary. The outer array must have the same lenght as the physical horizontal resolution of the display, 
and each of the sub-arrays must represent a column of the display (same vertical resolution), begining in the bottom-left corner of the display.

Any contributions to the code are welcome.

========================================================================

Ez egy python file a FOK-GYEM kijelzőkhöz, melyel soros porton keresztül, a megfelelő konvertálás után használatba vehetőek a kijelzők.
a file végén van egy pár példa a könnyebb használat érdekében.

Az alapvető parancsok lehívhatóak a send(VALID_COMMANDS["Clear") és hasonló parancsokkal, ahol az idézőjelek közötti részt ki kell cserélni a megfelelő parancsra.

Egyénki kijelzőkép küldéséhez kell egy 2D array, amiben az első array hossza megegyezik a kijelző valódi horizontális felbontásával. A belső array-ok maguk a kijelző pixeleinek oszlopai, 
a kijelző bal alsó sarkából indulva.
ezt a 2D-s arrays utána át kell adni a send_image() függvénynek kiegészítve a címmel és a protokollal. (lásd példa a file végén)

A kód tartalmaz optimalizálatlan vagy nem teljeskörűen tesztelt részeket, ezek helyes működésére, illetve a teszteletlen kód miatt az esetlegesen károsodó kijelzők miatt nem vállalok felelősséget.


