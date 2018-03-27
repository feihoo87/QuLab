import os


def beforeSaveFile(fname):
    '''makesure the path exists before save file'''
    dirname = os.path.dirname(fname)
    if not os.path.exists(dirname):
        os.makedirs(dirname)
