## General

Use xDelta UI to patch your clean (i.e. no anti-piracy patch has been applied) Black 2 or White 2 ROMs with the appropriate patch of your choice. The way to do it should be fairly self-explanatory.

Complete version includes all changes. Vanilla excludes the following:

- Any Pokémon changes except for compatibility with the three new TMs.
- Changes to Level Up movesets.
- Changes to Attacks.
- Certain trainers have their moves changed since they don't gain the new techniques they would in the Complete version.

The CRC32 for the ROMs should be as follows (this is viewable in WinRAR):

```
Pokémon Black 2 - 8A42D36E
Pokémon White 2 - B72BBA42
```

ROMs that are already patched will probably not be patchable with the BBVW content, though I'm not 100% sure.

The filenames for the ROMs in question should be:

```
Black 2 ~ iRiL-PkmnB2.rar
White 2 ~ mwl-pkmnw2u.rar
```

You'll have to find them yourself, though. Alternatively, back up your real cartridges!

Hopefully it works out for you. Happy playing!

- Dray

P.S: Those of you using no$gba/zoomer should probably check out this (link)[http://forum.romulation.net/index.php?topic=60304.0].

## xdelta UI

Version: 1.1

Author: KaioShin

Date: 31.05.09

### Introduction

xdelta is a binary patching program written by Josh McDonald, implementing the
VCDIFF delta compression standard. This little front-end was written in order
to make xdelta more foolproof to use for users who dislike to or don't know how to
use the command-line. This front-end was primarily written to be used by the
romhacking community to apply translations and other hacks to ROMs or other
binary files. xdelta itself can be used for tons of applications of course and
so should be this front-end. I did only test it with romhacking related tasks
though.

### Requirements

The program was written in C#, and therefore needs the .NET framework to function.
Google for it if you don't have it already. To be more specific it was compiled
with the .NET 2.0 framework.

### Why xdelta?

The romhacking community has been struggling with the need for a suitable
next-generation patching format for years now. One of the possible alternatives
for a widely accepted standard is xdelta. It has many unique features that make
it superior to formats like PPF or UPS.

Reasons to use xdelta:

- No filesize limitations
- Efficient handling of rebuilt filesystems and relocated data structures (This causes MASSIVE patch sizes on formats such as IPS or UPS)
- Protection against patching the wrong files

xdelta is currently the only patching standard that can handle rebuilt filesystems!

### How to Use

The GUI should be pretty self-explanatory. If xdelta throws an error it'll be displayed to
you. Refer to the xdelta documentation at http://xdelta.org/ for possible solutions in case
the error message isn't making sense to you. The most likely cause in the event of an error
is that you picked a wrong file. Note that you have to patch the same file with which the
patch creator created his patch from. Refer to the patch documentation to find out what
file that is.

The distribution package comes bundled with xdelta version 3.0u (Windows 32bit).
If there is a new release of xdelta just replace xdelta.exe with a binary of the
new version and it should be fine.

Note for Vista users: When you first use the front-end Vista will throw a warning asking you
to confirm that the front-end may launch xdelta. This is a protection so that no harmful
programs can call malware behind your back. You can safely accept the message and tell Vista
not to bother you again about it in the future.

You can associate patch files with the front-end. That way they'll be automatically opened by double clicking on patches. I recommend to associate _.xdelta files with the application and
save all your patches as _.xdelta files. To do this, just double click on a xdelta file and
tell windows to make xdeltaUI the default to open the file.

### Acknowledgement and Contact

Don't forget that xdelta itself was written by Josh McDonald. I (KaioShin) just wrote a GUI
to make it easier to use. All credits for the program should go to the original author.
I didn't ask for explicit permission to bundle a binary of xdelta with this front-end,
I assume it falls under fair-use. I'm not making any money of this program and I don't take
any kind of donations for it. If anyone who is directly involved with xdelta has a problem
with this please contact me and I'll distribute the front-end seperately.

If you find an error in the GUI (and not in xdelta itself!) you can contact me about it and
I'll try and fix it. You can reach me through a private message on the message board on
www.romhacking.net.

### Changelog

19.02.09 v1.0 - Initial Release
31.05.09 v1.1 - Patch files can now be associated to the patcher so they'll be automatically selected at startup. Thanks to Dragonsbrethren for the suggestion.
