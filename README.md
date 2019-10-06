# Mythrecmaze 

Automatically record the TV shows you follow on TVmaze.com using MythTV.

For usage instructions, please see https://htpc.tedsblog.org/2018/05/mythrecmaze.html.

Instead of or in addition to setting a recording using MythTV, follow your shows on tvmaze.com to have MythTV automatically record them.  A free or paid account on tvmaze.com is required.  The program checks the ical feed for the next seven days.  It then downloads guide data for the current day each time it is run and the next six days only if there is a change in the ical feed for those days.  It supports multiple API keys, so everyone in the house can have their own TVmaze account.

Notes:

Changing the MythTV xmltvid values is not required.  Mythrecmaze is compatible with other guide sources if the guide entries inserted from Mythrecmaze matching the recordings are not overwritten by the other guide source.

TVmaze is not limited to the USA, but this program currently works in the USA only.

Mythrecmaze has been tested using Ubuntu and Xubuntu with MythTV versions 28, 29 and 30.
