import hashlib
import os
import glob
import pathlib
from pathlib import Path
from ctypes.wintypes import MAX_PATH

from tkinter import filedialog, messagebox
from tkinter import Tk, Button, Label

from functools import partial
from unicodedata import normalize

version = "0.6"

error_file = "ACOUA_md5_errors.txt"


def log_message(message):
    f_err = open(error_file, "a")
    f_err.write(message + '\n')
    f_err.close()


def md5Checksum(filePath):
    with open(filePath, 'rb') as fh:
        m = hashlib.md5()
        while True:
            data = fh.read(8192)
            if not data:
                break
            m.update(data)
        return m.hexdigest()


def runchecksum(tkroot):
    # Clear all existing text messages
    for label in tkroot.winfo_children():
        if type(label) is Label:
            label.destroy()
    

    error_message = f"There were errors or warnings during processing:\ncheck {error_file} for information."
    error_file_header = "This is the acouachecksum log for errors and warnings. Do not archive.\n"

    d_title = "Select your ingestion folder"
    choosedir = filedialog.askdirectory(initialdir=Path.home(), title=d_title)
    if choosedir == '' or not os.path.exists(choosedir):
        return
    os.chdir(choosedir)

    # delete existing logfile unless it doesn't exist
    try:
        os.remove(error_file)
    except OSError:
        pass

    # Normalize base folder to the OS's convention, disregard askdirectory()'s weirdness
    choosedir = os.getcwd()

    path_info = Label(tkroot, text=f'Processing: {choosedir}')
    path_info.pack()
    tkroot.update()

    log_message(error_file_header)

    all_files = pathlib.Path(choosedir).rglob('**/*')
    files = []
    for ls in all_files:
        # print(os.path.join(str(ls.parents[0]), ls.name))
        if len(os.path.join(str(ls.parents[0]), ls.name)) > MAX_PATH:
            log_message(f"WARNING > {MAX_PATH} chars for path + file name: {os.path.join(str(ls.parents[0]), ls.name)}")
        filename = os.path.join(str(ls.parents[0]).replace(choosedir, '.'), ls.name)
        if not filename.endswith(os.sep + '.DS_Store') \
                and not filename.endswith(os.sep + 'Thumbs.db') \
                and not filename.startswith(os.path.join(choosedir, 'ACOUA_md5.md5')) \
                and not filename.startswith(os.path.join('.', 'ACOUA_md5.md5')) \
                and not os.path.isdir(filename):
            #filename = os.path.join([str(ls.parents[0]).replace(choosedir,'.'), ls.name])
            if filename.startswith('/'):
                files.append(filename[1:])
            else:
                files.append(filename)

    f = open("ACOUA_md5.md5", "wb")
    for element in files:
        try:
            md5 = md5Checksum(element)
            # filenames must be encoded as UTF-8, or they might not match what Libsafe sees on the filesystem
            # also: NFC normalization for proper (composed) representation of accented characters
            f.write(normalize('NFC',f'{md5} {element.replace(choosedir,".")}\n').encode("UTF-8"))
        except Exception as e:
            trace = str(e)
            log_message(trace)

    f.close()

    f_err = open(error_file, "r")
    error_content = f_err.read()
    f_err.close()
    """
    if error_content == error_file_header:
        os.remove(error_file)
    else:
        error_info = Label(tkroot, text=error_message)
        error_info.pack()
    """

    done_info = Label(tkroot, text=f'Done.')
    done_info.pack()
    messagebox.showinfo(title="Done", message="ACOUA_md5.md5 created")


root = Tk()
root.wm_title("ACOUA CheckSum v" + version)
root.geometry('400x250+1000+300')

button_label = 'Select a directory and run checksum'
Button(root, text=button_label, command=partial(runchecksum, root)).pack()
root.mainloop()
