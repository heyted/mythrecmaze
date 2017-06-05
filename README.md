# Mythrecmaze 

Automatically record the TV shows you follow on TVmaze.com using MythTV.

Mythrecmaze has been tested using Mythbuntu 16.04 with MythTV 0.28.

New in version 20170528:

Changing the MythTV xmltvid values is no longer required.  Mythrecmaze is now compatible with using another guide source with MythTV if the guide entries inserted from Tvmaze matching the recordings are not overwritten by the other guide source.

Version 20160802 is the last release to support MythTV 0.27.

Usage:

1.  If mythrecmaze has previously been installed, delete the file named "mythrecmaze.cfg."

2.  Click on “releases” above, and select the latest version.  

3.  Download and extract the files to your home folder. 

4.  If you start the PC daily, edit the MythTV autostart command using the line in autostart.txt, or run the program using some other method. 

Guide source option 1:  Edit the xmltvid values in the channel information section of mythweb/settings to match TVmaze id values.

Guide source option 2:

1.  The xmltvid values for a guide source other than using TVmaze as a guide source should already be configured, and there should be an xmltvid for each channel.

2.  Create a text file named “xmltvidmap.csv” which will match your xmltvid values to the corresponding TVmaze id values.  If xmltvidmap.csv does not exist, option one must be used.  If it does exist, option two must be used.

3.  Place xmltvidmap.csv in your home folder.

4.  Each line in the text file must have two entries separated by a comma.  Do not have any blank lines between the entries.  The first entry must match the current MythTV xmltvid value (not necessarily a number) and correspond to the TVmaze id number as the second entry.  An example  xmltvidmap.csv is shown below.  A few example lines are shown, and a typical file will have many more.

Example entries in  xmltvidmap.csv:
```
431,3
432,1
433,2
434,4
435,5
439,194
440,85
```
