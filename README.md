ACOUA EPFL Checksum helper tool
========

This repository contains the code source and the compiled version of the ACOUA checksum helper tool.
You can use this tool to generate the ```ACOUA_md5.md5```file needed for submitting your files into the EPFL ACOUA Archive system.


# How to use the tool

A full documentation can be found [here]() Note : Insert the KB link here when it's ready

The software for Windows and macos can be found here : [Releases](https://github.com/epfllibrary/acouachecksum/releases)

Linux user can use the source code to launch the program.

## Source code

* To create the environment ```python -m venv venv```
* To activate the environment ```source ./venv/bin/activate```
* to install the python package : ```pip install -r requirements.txt```
* To run the software ```python main.py```

## Files

* ```main.py``` : main python script
* ```README.md``` : this files
* ```requirements.txt``` : python packages (pip) needed for this project
* ```main-macos.spec``` : configuration file for pyinstaller for building MacOS package
* ```main-windows.spec``` : configuration file for pyinstaller for building Windows package


## Packaging (compilation)

You can generate a package of the application using pyinstaller.
Note: You need to run pyinstaller on the same system (ie for generating the macos package you need to run this command on macos for example)

* macos :  ```pyinstaller -y -w -F --distpath ./dist/macos main-macos.spec```
* windows : ```pyinstaller -y -w --name acouacheck -F --distpath ./dist/windows main-windows.spec ```

The corresponding package will be in the ```dist``` folder.
Note : the ```build``` folder is a temporary folder used by pyinstaller.

# Bash command equivalent

You can also generate the ```ACOUA_md5.md5``` in console (bash) using this command :

```find . -type f -not -name ".DS_Store" -not -name "ACOUA_md5.md5" -exec md5 -r '{}' \; > ./ACOUA_md5.md5```
