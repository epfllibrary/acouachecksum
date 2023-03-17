ACOUA EPFL Checksum helper tool
========

This repository contains the code source and the compiled version of the ACOUA checksum helper tool.
You can use this tool to generate the ```ACOUA_md5.md5```file needed for submitting your files into the EPFL ACOUA Archive system.


# How to use the tool

In the ACOUA Checksum tool, the user must select a directory containing a dataset to be archived (including the metadata.xml file).
The tool will calculate md5 checksums for all files except MacOS ```.DS_Store``` and Windows ```Thumbs.db```. By default, the tool will calculate checksums for files contained in Zip files under the selected directory and not the Zip files themselves, in order to be compatible with the Libsafe Archive Extractor. In agreement with the Libsafe behavior (sanitizers executed before the Archive Extractor),  ACOUA Checksum calculates checksums for ```.DS_Store``` and ```Thumbs.db``` files contained in Zip files.
The user can choose to calculate checksums for the Zip files instead of their content by unselecting the "Calculate checksum inside Zip files?" tick box.

In case the tool encounters errors, a warning will be displayed in the main window of the tool and the errors will be logged in the ```ACOUA_md5_errors.txt``` file.

The software for Windows and Macos can be found here : [Releases](https://github.com/epfllibrary/acouachecksum/releases)

Linux user can use the source code to launch the program as ```python main.py``` after installing the required modules from the requirements.txt file.

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

* macos :  ```pyinstaller -y --distpath ./dist/macos main-macos.spec```
* windows : ```pyinstaller -y --distpath ./dist/windows main-windows.spec```

The corresponding package will be in the ```dist``` folder.
Note : the ```build``` folder is a temporary folder used by pyinstaller.

# Bash command equivalent

You can also generate the ```ACOUA_md5.md5``` in console (bash) using this command, but character encoding problems are possible (the output file must be UTF-8) :

```find . -type f -not -name ".DS_Store" -not -name "ACOUA_md5.md5" -exec md5 -r '{}' \; > ./ACOUA_md5.md5```
