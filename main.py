import hashlib
import os
import sys
import glob
import pathlib
import shutil
import zipfile
import py7zr
import tarfile
import rarfile
from pathlib import Path
from ctypes.wintypes import MAX_PATH

import collections

import tkinter as tk
from tkinter import font, filedialog, ttk

from functools import partial
from unicodedata import normalize

version = "0.9"

error_file = "ACOUA_md5_errors.txt"

# expected path of the ingestion folder...
# we use the test value, which is a bit longer
libsafe_ingestion_path = "//nas-app-ma-cifs1.epfl.ch/si_datarepo_inj_test_app/LIBSAFE/ING/ING*******/"
backslash = '\\'

compressed_extensions = ('.zip', '.7z', '.rar', '.tar')
multipart_hint_extensions = ('.z01', '.z001', '.part1.rar')


def remove_archiver():
    selected_checkboxs = listbox.curselection()
    for selected_checkbox in selected_checkboxs[::-1]:
        listbox.delete(selected_checkbox)


def add_archiver(arch_format):
    listbox.insert("end", arch_format)


# A few generic functions to handle divergences between main classes:
# from modules zipfile, py7zr, etc. .

def open_archive(ls, extension, parent=None):
    # IN PROGRESS what should archivename be if ls is an archive within another archive?
    if parent is None:
        print('ls is a', type(ls))
        if isinstance(ls, pathlib.PosixPath):
            archivename = os.path.join(str(ls.parents[0]), ls.name)
        elif isinstance(ls, str):
            archivename = ls
        elif isinstance(ls, zipfile.ZipFile):
            archivename = archive_filename(ls)
        elif isinstance(ls, zipfile.ZipExtFile):
            archivename = archive_filename(ls)
        elif isinstance(ls, py7zr.SevenZipFile):
            archivename = archive_filename(ls)
        elif isinstance(ls, tarfile.TarFile):
            archivename = archive_filename(ls)
        elif isinstance(ls, rarfile.RarFile):
            archivename = archive_filename(ls)
        else:
            archivename = '[dummy]'

        try:
            if extension == '.zip':
                return (archivename, zipfile.ZipFile(archivename, mode="r"))
            if extension == '.7z':
                return (archivename, py7zr.SevenZipFile(archivename, mode="r"))
            if extension == '.rar':
                return (archivename, rarfile.RarFile(archivename, mode="r"))
            if extension == '.tar':
                return (archivename, tarfile.TarFile(archivename, mode="r"))
        except (zipfile.BadZipFile,
                py7zr.exceptions.Bad7zFile,
                rarfile.NotRarFile,
                tarfile.ReadError) as e:
            trace = str(e)
            log_message(trace)
            log_message(f"{archivename} is not a valid {extension} file.")
            return (archivename, None)
    else:
        print(ls)
        if isinstance(ls, zipfile.ZipInfo):
            try:
                subarch = zipfile.ZipFile(parent.open(ls, mode='r'), mode='r')
                archivename = f"{archive_filename(parent)}##{archive_filename(ls)}]"
                print(archivename, subarch)
                return (archivename, subarch)
            except zipfile.BadZipFile:
                return (None, None)
        elif isinstance(ls, zipfile.ZipExtFile):
            archivename = f"{archive_filename(parent)}##{archive_filename(ls)}]"
            return (archivename, ls)
        elif isinstance(ls, py7zr.SevenZipInfo):
            try:
                pass
            except py7zr.exceptions.Bad7zFile:
                return (None, None)
        elif isinstance(ls, rarfile.RarInfo):
            try:
                pass
            except rarfile.NotRarFile:
                return (None, None)
        elif isinstance(ls, tarfile.TarInfo):
            try:
                pass
            except tarfile.ReadError:
                return (None, None)


def archive_content(archive):
    if archive is None:
        return []
    if isinstance(archive, zipfile.ZipFile):
        return archive.infolist()
    if isinstance(archive, py7zr.SevenZipFile):
        return archive.list()
    if isinstance(archive, tarfile.TarFile):
        return archive.getmembers()
    if isinstance(archive, rarfile.RarFile):
        return archive.infolist()


def archive_filename(archive):
    if isinstance(archive, zipfile.ZipFile):
        return archive.filename
    if isinstance(archive, zipfile.ZipExtFile):
        return archive.name
    if isinstance(archive, py7zr.SevenZipFile):
        return archive.filename
    if isinstance(archive, tarfile.TarFile):
        return archive.filename
    if isinstance(archive, rarfile.RarFile):
        return archive.filename
    if isinstance(archive, zipfile.ZipInfo):
        return archive.filename
    if isinstance(archive, py7zr.ArchiveInfo):
        return archive.filename
    if isinstance(archive, tarfile.TarInfo):
        return archive.filename
    if isinstance(archive, rarfile.RarInfo):
        return archive.filename


def isdir(arch_object):
    if isinstance(arch_object, zipfile.ZipInfo):
        return arch_object.is_dir()
    if isinstance(arch_object, py7zr.FileInfo):
        return arch_object.is_directory
    if isinstance(arch_object, tarfile.TarInfo):
        return arch_object.isdir()
    if isinstance(arch_object, rarfile.RarInfo):
        return arch_object.isdir()


def archive_object_filename(arch_object):
    if isinstance(arch_object, zipfile.ZipInfo):
        return arch_object.filename
    if isinstance(arch_object, py7zr.FileInfo):
        return arch_object.filename
    if isinstance(arch_object, tarfile.TarInfo):
        return arch_object.name
    if isinstance(arch_object, rarfile.RarInfo):
        return arch_object.filename


def log_message(message):
    f_err = open(error_file, "a")
    f_err.write(message + '\n')
    f_err.close()


def is_cp850(s):
    # check whether filenames are encoded as cp850 **sigh** or utf-8
    try:
        x = s.encode('cp850').decode('utf-8')
        return True
    except Exception as e:
        trace = str(e)
        log_message(trace)
        return False


def md5Checksum(filePath, ziparchive=None):
    # blocksize = 8192
    # switch to 1MB blocks to improve performance
    blocksize = 2**20
    if ziparchive is None:
        fh = open(filePath, 'rb')
    elif isinstance(ziparchive, py7zr.SevenZipFile):
        # Use the BytesIO part of the response, the filename can be discarded
        ziparchive.reset()
        fname, fh = list(ziparchive.read(filePath).items())[0]
    elif isinstance(ziparchive, tarfile.TarFile):
        tmp_checksum_folder = 'tmp_checksum_folder'
        ziparchive.extract(filePath, path=tmp_checksum_folder)
        fh = open(tmp_checksum_folder + os.sep + filePath, 'rb')
        shutil.rmtree(tmp_checksum_folder)
    else:
        fh = ziparchive.open(filePath, 'r')

    m = hashlib.md5()
    while True:
        data = fh.read(blocksize)
        if not data:
            break
        m.update(data)
    return m.hexdigest()


def runchecksum(tkroot, width_chars, check_zips):
    # Clear all existing text messages
    do_zips = bool(check_zips.get())

    if do_zips:
        archiver_list = listbox.get(0, tk.END)
    else:
        archiver_list = []
    if len(archiver_list) == 0:
        archiver_list = ['.zip']
    print('archiver list', archiver_list)

    for label in tkroot.winfo_children():
        if type(label) is tk.Label:
            label.destroy()

    error_message = f"There were errors or warnings during processing:\n"
    error_message += f"check {error_file} for information."
    error_file_header = f"This is the acouachecksum log for errors and warnings. Do not archive.\n"

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

    # Normalize base folder to the OS's convention
    # (disregard askdirectory()'s weirdness)
    choosedir = os.getcwd()
    # get folder name, useful to check for path length
    foldername = choosedir.split(os.sep)[-1]

    choosedir_display = ''
    line_length = 0
    for fs_level in choosedir.split(os.sep):
        if len(fs_level) > width_chars:
            fs_level = fs_level[0:width_chars-6] + '[...]'

        if line_length + len(fs_level) < width_chars:
            choosedir_display += fs_level + os.sep
            line_length += len(fs_level) + 1
        else:
            choosedir_display += '\n'
            choosedir_display += fs_level + os.sep
            line_length = len(fs_level) + 1

    path_info = tk.Label(tkroot, text=f'Processing:\n{choosedir_display}')
    path_info.pack()
    tkroot.update()

    # Create logfile for potential warnings and errors
    log_message(error_file_header)

    all_files = list(pathlib.Path(choosedir).rglob('**/*'))
    for hint in multipart_hint_extensions:
        for file in all_files:
            if file.name.endswith(hint):
                log_message(f"{file.name} seems to be part of a multipart archive.")
                log_message("=> this is not supported and will probably fail.")

    # TODO compressed formats are not processed simultaneously, this needs to be adapted
    # 
    arch_files = []
    if do_zips:
        for (idx, extension) in enumerate(archiver_list):
            if idx == 0 or (extension not in archiver_list[0:idx-1]):
                arch_files.append(list(pathlib.Path(choosedir).rglob(f'**/*{extension}')))

        nonzipfiles = [x for x in all_files if not any([x.name.endswith(ext) for ext in archiver_list])]

    else:
        nonzipfiles = all_files
        for extension in compressed_extensions:
            arch_files.append((extension, []))
            arch_backlog[extension] = []

    print('arch:', arch_files)
    print('non arch', nonzipfiles)

    files = []
    final_filelist = []
    # Create tk.Tk label for progress information: counting files
    progress_update_frequency = 10
    progress_info = tk.Label(tkroot, text=f'Listing: {len(files)} files')
    progress_info.pack()
    tkroot.update()
    for ls in nonzipfiles:
        # check for excessive path length locally
        # (in case the user has a problem)
        if len(os.path.join(str(ls.parents[0]), ls.name)) > MAX_PATH:
            log_message(f"WARNING > {MAX_PATH} chars for path + file name:")
            log_message(f"-> {os.path.join(str(ls.parents[0]), ls.name)}")
        filename = os.path.join(str(ls.parents[0]).replace(choosedir, '.'),
                                ls.name)
        if not filename.endswith(os.sep + '.DS_Store') \
           and not filename.endswith(os.sep + 'Thumbs.db') \
           and not filename.startswith(os.path.join(choosedir, 'ACOUA_md5.md5')) \
           and not filename.startswith(os.path.join('.', 'ACOUA_md5.md5')) \
           and not filename.startswith(os.path.join(choosedir, error_file)) \
           and not filename.startswith(os.path.join('.', error_file)) \
           and not os.path.isdir(filename):
            # check for excessive expected path length locally
            # (where libsafe will fail)
            target_path = libsafe_ingestion_path + foldername + filename[1:]
            # print(target_path)
            if len(target_path) > MAX_PATH:
                log_message(f"WARNING > {MAX_PATH} chars for expected path + file name:")
                log_message(f"-> {target_path}")
            # filename = os.path.join([str(ls.parents[0]).replace(choosedir,'.'), ls.name])
            if filename.startswith('/'):
                files.append(filename[1:])
            else:
                files.append(filename)

        if len(files) % progress_update_frequency == 0:
            # print(f'Listing: {len(files)} files')
            progress_info.config(text=f'Listing: {len(files)} files')
            tkroot.update()

    final_filelist += [f.lower() for f in files]

    arch_content = {}
    for extension in archiver_list:
        arch_content[extension] = {}

    n_archived_files = 0
    # TODO adapt to process arch_content, then switch to subsequent formats in arch_backlog
    for idx, extension in enumerate(archiver_list):
        for ls in arch_files[idx]:
            # Libsafe Sanitizers are run before the Archive Extractor
            # => .DS_Store and Thumbs.db will not be deleted if contained in an archive files
            (archivename, archive) = open_archive(ls, extension)
            arch_content[extension][archivename] = []
            # TODO: implement behvior for content that would be extension[idx+1] in the sequence
            # TODO: there could other sub archives further down the sequence as well...
            for info in archive_content(archive):
                print(archive_object_filename(info))
                if idx <= len(archiver_list) - 2:
                    if archive_object_filename(info).endswith(archiver_list[idx+1]):
                        print(f"Within {ls} : found {archive_object_filename(info)}")
                        (subarchname, sub_arch) = open_archive(info, archiver_list[idx+1], parent=archive)
                        if sub_arch is not None:
                            for x in archive_content(sub_arch):
                                print('sub_arch contains:', x)
                if not isdir(info):
                    arch_content[extension][archivename].append(archive_object_filename(info))

            for content_file in arch_content[extension][archivename]:
                # check for excessive expected path length locally (where libsafe will fail)
                target_path = libsafe_ingestion_path + foldername + '/' + content_file
                final_filelist.append(target_path.lower())
                if len(target_path) > MAX_PATH:
                    log_message(f"WARNING > {MAX_PATH} chars for expected path + file name:")
                    log_message(f"-> {target_path}")

            n_archived_files += len(arch_content[extension][archivename])
            progress_msg = f'Listing: {len(files) + n_archived_files} files'
            progress_info.config(text=progress_msg)
            tkroot.update()
    total_files = len(files) + n_archived_files

    # check for full path !+ filename collisions that will result in data loss and/or ingestion errors
    name_collisions = [(item, count) for item, count in collections.Counter(final_filelist).items() if count > 1]
    for conflict in name_collisions:
        log_message(f"Name conflict: {conflict[0]} will occur {conflict[1]} times in your dataset (probably from several compressed files).")

    # print('Done listing')
    # now display the actual checksum progress
    progress_update_frequency = 1
    progress = 0
    progress_info .config(text=f'Checksum progress: {progress}/{total_files}')
    tkroot.update()

    f = open("ACOUA_md5.md5", "wb")

    for element in files:
        progress += 1
        try:
            md5 = md5Checksum(element)
            # In order to match what Libsafe sees on the filesystem:
            # - filenames must be encoded as UTF-8
            # - NFC normalization for representation of accented characters
            f.write(normalize('NFC', f'{md5} {element.replace(choosedir, ".").replace("/", backslash)}\n').encode("UTF-8"))
        except Exception as e:
            trace = str(e)
            log_message(trace)
        if progress % progress_update_frequency == 0:
            # print(f'Progress: {progress}/{len(files)}')
            progress_info.config(text=f'Progress: {progress}/{total_files}')
            tkroot.update()

    for extension in archiver_list:
        for myarchfile in arch_content[extension]:
            (archivename, archive) = open_archive(myarchfile, extension)
            archive_path = os.path.sep.join(myarchfile.split(os.sep)[0:-1])
            archive_path = archive_path.replace(choosedir, '.')
            # print(archive_path)
            for archived_file in arch_content[extension][myarchfile]:
                # Filenames of objects inside a zip are either:
                # 1) cp850/cp437 (old style)
                # 2) utf-8. Let's check
                assumed_encoding = 'cp850' if is_cp850(archived_file) else 'utf-8'
                progress += 1
                try:
                    md5 = md5Checksum(archived_file, ziparchive=archive)
                    # In order to match what Libsafe sees on the filesystem:
                    # - filenames must be encoded as UTF-8
                    # - NFC normalization is not needed: the Libsafe Archive Extractor will manage
                    f.write(f'{md5} {archive_path + os.path.sep + archived_file.encode(assumed_encoding).decode("utf-8")}\n'.replace("/", backslash).encode("UTF-8"))
                except Exception as e:
                    trace = str(e)
                    log_message(trace)
                if progress % progress_update_frequency == 0:
                    progress_msg = f'Progress: {progress}/{total_files}'
                    progress_info.config(text=progress_msg)
                    tkroot.update()

    f.close()
    progress_info.config(text=f'Progress: {progress}/{total_files}')
    tkroot.update()

    f_err = open(error_file, "r")
    error_content = f_err.read()
    f_err.close()

    if error_content.replace('\r', '').replace('\n', '') == error_file_header.replace('\r', '').replace('\n', ''):
        os.remove(error_file)
    else:
        error_info = tk.Label(tkroot, text=error_message)
        error_info.pack()

    done_info = tk.Label(tkroot, text='Done: ACOUA_md5.md5 has been created')
    done_info.pack()


root = tk.Tk()
current_font = font.nametofont("TkDefaultFont")
root.wm_title("ACOUA CheckSum v" + version)
width = 400
width_chars = int(1.7*width / current_font.actual()['size'])
root.geometry(f'{width}x550+1000+300')
check_zips = tk.IntVar()
check_zips.set(1)
checkbutton_label = "Calculate checksum inside Zip and similar files?"
tk.Checkbutton(root, text=checkbutton_label, variable=check_zips).pack()
zip_select_lbl = tk.Label(root, text="Zip-like format sequence:")
zip_select_lbl.pack()
frm = tk.Frame()
listbox = tk.Listbox(frm,  selectmode=tk.MULTIPLE)
# 2023-11-01 We will only use one single format for now
listbox.insert(1, ".zip")
#listbox.insert(2, ".7z")
#listbox.insert(3, ".rar")
#listbox.insert(4, ".zip")

scrollbar = ttk.Scrollbar(frm, orient='vertical')
listbox.config(yscrollcommand=scrollbar.set)
scrollbar.config(command=listbox.yview)

btn_frm = tk.Frame()
for arch_format in compressed_extensions:
    callback = partial(add_archiver, arch_format)
    tk.Button(btn_frm,
              text=f"Add {arch_format}",
              command=callback).pack(side=tk.LEFT)
btn_frm.pack()
delete_btn = tk.Button(root, text="Delete selected", command=remove_archiver)

scrollbar.pack(side=tk.RIGHT, fill=tk.BOTH)
listbox.pack()
frm.pack()
delete_btn.pack()

button_label = 'Select a directory and run checksum'
callback = partial(runchecksum, root, width_chars, check_zips)
tk.Button(root, text=button_label, command=callback).pack()
root.mainloop()
