import re
data = open(r'D:\CS 1.6 GoldClient\MetaHook.exe','rb').read()
i = data.find(b'plugins.lst')
print('ascii at', i)
print(repr(data[i-300:i+200]))
# wide
w = 'plugins.lst'.encode('utf-16le')
j = data.find(w)
print('wide at', j)
print(repr(data[j-300:j+200]))
