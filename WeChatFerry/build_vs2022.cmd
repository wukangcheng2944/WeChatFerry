@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d %~dp0

set "CONFIG=%~1"
if "%CONFIG%"=="" set "CONFIG=Release"

set "PF86=C:\Program Files (x86)"
set "VSDEVCMD="
if exist "%PF86%\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat" set "VSDEVCMD=%PF86%\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat"
if not defined VSDEVCMD (
    if exist "!PF86!\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat" set "VSDEVCMD=!PF86!\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat"
)
if not defined VSDEVCMD (
    if exist "!PF86!\Microsoft Visual Studio\2022\Professional\Common7\Tools\VsDevCmd.bat" set "VSDEVCMD=!PF86!\Microsoft Visual Studio\2022\Professional\Common7\Tools\VsDevCmd.bat"
)
if not defined VSDEVCMD (
    if exist "!PF86!\Microsoft Visual Studio\2022\Enterprise\Common7\Tools\VsDevCmd.bat" set "VSDEVCMD=!PF86!\Microsoft Visual Studio\2022\Enterprise\Common7\Tools\VsDevCmd.bat"
)

if not defined VSDEVCMD (
    echo VsDevCmd.bat not found
    exit /b 1
)

call "%VSDEVCMD%" -arch=x64 -host_arch=x64
if errorlevel 1 exit /b 1

if exist "C:\Tools\vcpkg\vcpkg.exe" (
    set "VCPKG_ROOT=C:\Tools\vcpkg"
)
if not defined VCPKG_ROOT set "VCPKG_ROOT=C:\Tools\vcpkg"
set "CI=true"
set "WCF_AUTO_ACCEPT_LICENSE=true"
set "SOLUTION_DIR=%CD%\"

if not exist "!VCPKG_ROOT!\vcpkg.exe" (
    echo VCPKG_ROOT is invalid: !VCPKG_ROOT!
    exit /b 1
)

if exist "vcpkg_installed\x64-windows-static\lib\fmt.lib" (
    echo [1/4] vcpkg dependencies already present
) else (
    echo [1/4] Install vcpkg dependencies
    "!VCPKG_ROOT!\vcpkg.exe" install --triplet x64-windows-static
    if errorlevel 1 exit /b 1
)

echo [2/4] Generate protobuf sources
pushd rpc\proto
call ..\tool\protoc.bat --nanopb_out=. wcf.proto
if errorlevel 1 (
    popd
    exit /b 1
)
popd

echo [3/4] Build SDK
msbuild sdk\SDK.vcxproj ^
  /m ^
  /t:Build ^
  /p:Configuration=%CONFIG% ^
  /p:Platform=x64 ^
  /p:SolutionDir=%SOLUTION_DIR% ^
  /p:VcpkgTriplet=x64-windows-static ^
  /p:VcpkgEnableManifest=true ^
  /verbosity:minimal
if errorlevel 1 exit /b 1

echo [4/4] Build Spy
msbuild spy\Spy.vcxproj ^
  /m ^
  /t:Build ^
  /p:Configuration=%CONFIG% ^
  /p:Platform=x64 ^
  /p:SolutionDir=%SOLUTION_DIR% ^
  /p:VcpkgTriplet=x64-windows-static ^
  /p:VcpkgEnableManifest=true ^
  /p:PreBuildEventUseInBuild=false ^
  /p:PostBuildEventUseInBuild=false ^
  /verbosity:minimal
if errorlevel 1 exit /b 1

if not exist Out md Out

set "SPY_TARGET=Spy"
if /I "%CONFIG%"=="Debug" set "SPY_TARGET=Spy_debug"
if /I "%CONFIG%"=="Dev" set "SPY_TARGET=Spy_debug"

copy /y "x64\%CONFIG%\SDK.dll" "Out\SDK.dll" >nul
copy /y "x64\%CONFIG%\%SPY_TARGET%.dll" "Out\Spy.dll" >nul
copy /y "x64\%CONFIG%\%SPY_TARGET%.exp" "Out\Spy.exp" >nul
copy /y "x64\%CONFIG%\%SPY_TARGET%.lib" "Out\Spy.lib" >nul
copy /y "x64\%CONFIG%\%SPY_TARGET%.pdb" "Out\Spy.pdb" >nul
copy /y "DISCLAIMER.md" "Out\DISCLAIMER.md" >nul

if exist "..\clients\python\wcferry" (
    copy /y "x64\%CONFIG%\SDK.dll" "..\clients\python\wcferry\SDK.dll" >nul
    copy /y "x64\%CONFIG%\%SPY_TARGET%.dll" "..\clients\python\wcferry\spy.dll" >nul
    copy /y "DISCLAIMER.md" "..\clients\python\wcferry\DISCLAIMER.md" >nul
)

echo Build complete
exit /b 0
