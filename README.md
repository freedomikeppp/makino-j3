# makino-j3
マキノJ3シリーズにFANUC FOCASライブラリを使って通信するPythonのサンプルです。

Windows環境で、専用のライブラリを利用することで動作します。

自身の環境で実装する際のヒントとしてお使い下さい。

# 実装機能
- DデバイスとRデバイスへの値の読み込みと書き込み
- NC内のディレクト検索とファイルの操作（read・write・delete）

# 参考情報

## 以下のdllが必要です
- fwlibe64.dll

## ライブラリドキュメント
http://alvarestech.com/temp/mtconnect/mtconnect-adapter-f9e4039ec1e48cd3f2de9b4a58309d69247a97f5/GE%20Fanus%20Focas%20Lib%202.5/GE%20Fanus%20Focas%20Lib%202.5/Document/SpecJ/FWLIB32.HTM

# 使い方

```
# Open connection
j3 = J3.get_connection('192.168.1.10:8193')

# Dデバイスへの操作
j3.write_dev('D11600', 255)
j3.read_dev('D11600') # -> 255

j3.write_dev('D11600', 256, size=2)
j3.read_dev('D11600', size=2) # -> 256
j3.read_dev('D11600') # -> 0
j3.read_dev('D11601') # -> 1
j3.read_dev('D11602') # -> 0

# Rデバイスへの操作
j3.write_dev('R6653.0',1)
j3.write_dev('R6653.1',0)
j3.write_dev('R6653.2',1)
j3.write_dev('R6653.3',0)
j3.write_dev('R6653.4',1)
j3.write_dev('R6653.5',0)
j3.write_dev('R6653.6',1)
j3.write_dev('R6653.7',0)
j3.read_dev('R6653') # -> 85

# 加工プログラムのファイルの操作（read・write・delete）
data = b'O8990\nG4 X10.\nM30\n%'
j3.write_file('//CNC_MEM/USER/LIBRARY/O8990', data)
j3.read_file('//CNC_MEM/USER/LIBRARY/O8990')
j3.delete_file('//CNC_MEM/USER/LIBRARY/O8990')

# Close connection
j3.close()
```
