import hashlib
import os
import glob
import pathlib
from pathlib import Path
from tkinter import filedialog, messagebox
from tkinter import Tk, Button, Label
from functools import partial
from unicodedata import normalize

version = "0.6"

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

    for label in tkroot.winfo_children():
        if type(label) is Label:
            label.destroy()

    d_title = "Select your ingestion folder"
    choosedir = filedialog.askdirectory(initialdir=Path.home(), title=d_title)
    if choosedir == '' or not os.path.exists(choosedir):
        return
    os.chdir(choosedir)

    # Normalize base folder to the OS's convention, disregard askdirectory()'s weirdness
    choosedir = os.getcwd()

    path_info = Label(tkroot, text=f'Processing: {choosedir}')
    path_info.pack()
    tkroot.update()

    all_files = pathlib.Path(choosedir).rglob('**/*')
    files = []
    for ls in all_files:
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
        md5 = md5Checksum(element)
        # filenames must be encoded as UTF-8, or they might not match what Libsafe sees on the filesystem
        # also: NFC normalization for proper (composed) representation of accented characters
        f.write(normalize('NFC',f'{md5} {element.replace(choosedir,".")}\n').encode("UTF-8"))

    f.close()
    done_info = Label(tkroot, text=f'Done.')
    done_info.pack()
    messagebox.showinfo(title="Done", message="ACOUA_md5.md5 created")


root = Tk()
root.wm_title("ACOUA CheckSum v" + version)
root.geometry('400x250+1000+300')

button_label = 'Select a directory and run checksum'
Button(root, text=button_label, command=partial(runchecksum, root)).pack()
root.mainloop()
