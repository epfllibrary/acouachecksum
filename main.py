import hashlib
import os
import glob
from pathlib import Path
from tkinter import filedialog, messagebox
from tkinter import Tk, Button

version = "0.2"

def md5Checksum(filePath):
    with open(filePath, 'rb') as fh:
        m = hashlib.md5()
        while True:
            data = fh.read(8192)
            if not data:
                break
            m.update(data)
        return m.hexdigest()


def runchecksum():
    d_title = "Select your ingestion folder"
    choosedir = filedialog.askdirectory(initialdir=Path.home(), title=d_title)
    if choosedir == '' or not os.path.exists(choosedir):
        return
    os.chdir(choosedir)

    all_files = glob.glob(choosedir + '**/**', recursive=True)
    files = []
    for ls in all_files:
        if not ls.startswith(os.path.join(choosedir, '.')) \
                and not ls.startswith(os.path.join(choosedir, '.DS_Store')) \
                and not ls.startswith(os.path.join(choosedir, 'ACOUA_md5.md5')) \
                and not os.path.isdir(os.path.join(choosedir, ls)):
            files.append(ls)

    f = open("ACOUA_md5.md5", "w")
    for element in files:
        md5 = md5Checksum(element)
        f.write(f'{md5} {element.replace(choosedir,".")}\n')
    f.close()
    messagebox.showinfo(title="Done", message="ACOUA_md5.md5 created")


root = Tk()
root.wm_title("ACOUA CheckSum v" + version)
root.geometry('400x250+1000+300')

button_label = 'Select a directory and run checksum'
Button(root, text=button_label, command=runchecksum).pack()
root.mainloop()
