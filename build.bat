@echo off
rem ===================================================================
rem  DSPET build  -  16-bit Windows 3.0 target (Open Watcom 2.0)
rem
rem  WATCOM must point at the Open Watcom root.  Note that
rem  %WATCOM%\binnt64 has to be on PATH: that is where wlink finds its
rem  system definitions file (wlink.lnk), and without it every link
rem  fails with "undefined system name: windows".
rem
rem  Produces  dist\DSPET.exe  plus the DOS tools dist\JOIN.exe,
rem  dist\CRC.exe.  Then run  python tools\mkfloppy.py G:\  to put the
rem  whole set on a diskette.
rem ===================================================================
setlocal
if "%WATCOM%"=="" set WATCOM=C:\WATCOM
set PATH=%WATCOM%\binnt64;%WATCOM%\binw;%PATH%
set INCLUDE=%WATCOM%\h;%WATCOM%\h\win
set LIB=%WATCOM%\lib286;%WATCOM%\lib286\win

if not exist build mkdir build
if not exist dist  mkdir dist

echo [1/3] compiling the Windows program...
set WF=-bt=windows -ml -os -zq -3 -i=inc -i=%WATCOM%\h\win
wcc %WF% -fo=build\main.obj src\main.c || goto :err
wcc %WF% -fo=build\spr.obj  src\spr.c  || goto :err
wcc %WF% -fo=build\snd.obj  src\snd.c  || goto :err
wcc %WF% -fo=build\menu.obj src\menu.c || goto :err
wcc %WF% -fo=build\link.obj src\link.c || goto :err

echo [2/3] linking DSPET.exe...
wlink @build\dspet.lnk || goto :err

echo [3/3] compiling the DOS tools...
set DF=-bt=dos -ml -os -zq -3 -i=%WATCOM%\h
wcc %DF% -fo=build\join.obj src\dos\join.c || goto :err
wcc %DF% -fo=build\crc.obj  src\dos\crc.c  || goto :err
wlink @build\join.lnk || goto :err
wlink @build\crc.lnk  || goto :err

echo.
echo done:
dir /b dist
exit /b 0

:err
echo.
echo *** BUILD FAILED ***
exit /b 1
