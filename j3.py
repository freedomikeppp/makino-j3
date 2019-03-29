# coding: utf-8
'''
マキノJ通信クラス
'''
from os import path
from ctypes import *
from enum import Enum
import threading
import traceback


class J3:

    #同一スレッド内で同一ホストの接続は同じインスタンスを使う
    __connections = {}
    @classmethod
    def get_connection(cls, host):
        key = str(threading.current_thread().ident) + "_" + host
        if key not in cls.__connections:
            cls.__connections[key] = J3(host)
        return cls.__connections[key]

    __ip = None
    __port = None
    __isopen = False
    __handle = None
    __dll = cdll.LoadLibrary(path.join(path.dirname(path.abspath(__file__)), 'Fwlibe64.dll'))
    __lock = threading.RLock()
    __offset_dict = {
        0: 0b00000001, 1: 0b00000010, 2: 0b00000100, 3: 0b00001000,
        4: 0b00010000, 5: 0b00100000, 6: 0b01000000, 7: 0b10000000
    }

    def __init__(self, host):
        '''
        Args:
            host: IPアドレス:ポート番号
        '''
        self.__ip, self.__port = host.split(':')

    def __str__(self):
        return self.__ip + ":" + self.__port + " " + ("Open" if self.__isopen else "Close")

    def __del__(self):
        '''アプリケーション終了時、またはオブジェクトがどこからも参照されていなくなった際に実行される。'''
        self.close()

    def __open(self):
        '''NCに接続し、ライブラリハンドルを取得します。'''
        if not self.__isopen:
            self.__dll.cnc_allclibhndl3.restype = c_short
            self.__dll.cnc_allclibhndl3.argtypes = (c_char_p, c_ushort, c_long, POINTER(c_ushort))
            handle = c_ushort()
            res = self.__dll.cnc_allclibhndl3(bytes(self.__ip, 'utf-8'), c_ushort(int(self.__port)), c_long(10), byref(handle))
            self.__cnc_raise_error(res)
            self.__handle = handle
            self.__isopen = True

    def close(self):
        '''ライブラリハンドルを解放します。'''
        if self.__isopen:
            self.__dll.cnc_freelibhndl.restype = c_short
            self.__dll.cnc_freelibhndl.argtypes = (c_ushort,)
            res = self.__dll.cnc_freelibhndl(self.__handle)
            self.__cnc_raise_error(res)
            self.__isopen = False
        else:
            pass

    def is_open(self):
        '''__open()処理後、接続が開いているか確認する。
        
        Return:
            bool: 接続が開いているならTrue
        '''
        with self.__lock:
            try:
                self.__open()
            except:
                pass
            return self.__isopen

    # --- NCプログラムファイル操作関連 ---

    def exist_file(self, path):
        '''NCプログラム検索し、存在判定をboolで返す。
        
        Args:
            path (str): 絶対パス
        Return:
            bool: ファイルが存在するならTrue
        '''
        filenm = path.split('/')[-1]
        if filenm[0:1] != 'O':
            raise Exception('加工PG(先頭がOの番号)のみ検索可能。')
        with self.__lock:
            self.__open()
            self.__dll.cnc_search.restype = c_short
            self.__dll.cnc_search.argtypes = (c_ushort, c_short)
            res = self.__dll.cnc_search(self.__handle, c_short(int(filenm[1:])))
            if res == 0:
                return True
            elif res == 5:
                return False
            else:
                self.__cnc_raise_error(res)

    def read_file(self, path):
        '''NCプログラムを読み込む。
        
        Args:
            path (str): 絶対パス
        Return:
            bytes: プログラムの中身をバイナリで返す
        '''
        with self.__lock:
            self.__open()
            result = b''

            if not self.exist_file(path):
                raise Exception('指定された加工プログラムが存在しません。(path: ' + str(path) + ')')

            # EW_DATA(5): データの誤り の詳細エラー内容
            ew_data_errmap = {
                2 : '指定範囲内にプログラムが登録されていない。',
                3 : 'NCプログラム領域が壊れています。'}

            # 返り値と引数定義
            self.__dll.cnc_upstart4.restype = c_short
            self.__dll.cnc_upstart4.argtypes = (c_ushort, c_short, c_char_p)
            self.__dll.cnc_upload4.restype = c_short
            self.__dll.cnc_upload4.argtypes = (c_ushort, POINTER(c_long), c_char_p)
            self.__dll.cnc_upend4.restype = c_short
            self.__dll.cnc_upend4.argtypes = (c_ushort,)

            try:
                # CNC側にNCプログラムのRead開始を要求
                data_type = c_short(0) # 0: NC指令プログラム
                file_name_p = c_char_p(create_string_buffer(bytes(path, 'utf-8')).raw) # Readするファイル名
                res = self.__dll.cnc_upstart4(self.__handle, data_type, file_name_p)
                self.__cnc_raise_error(res)

                # NCデータのReadを行う
                data_p = c_char_p(create_string_buffer(1024).raw)
                while True:
                    length_p = c_long(1024) # ポインタ実際に出力された文字数がセットされます
                    res = self.__dll.cnc_upload4(self.__handle, byref(length_p), data_p)

                    # EW_OK（正常完了）
                    if res == 0:
                        begin_len = 2 if data_p.value.find(b'%\n') != 1 else None # 先頭の場合、先頭文字のb'%\n'を取り除く
                        last_position = data_p.value.find(b'\n%') # 行末文字のb'\n%'が何行目か検索
                        end_len = last_position if last_position != -1 else None
                        result += data_p.value[begin_len:end_len]
                        # 末文字があればRead終了
                        if last_position != -1:
                            break
                    # EW_DATA (エラー詳細あり)
                    elif res == 5:
                        detail_err = self.__cnc_getdtailerr()
                        raise Exception(ew_data_errmap[detail_err])
                    # EW_BUFFER（バッファがフル状態なのでリトライ）
                    elif res == 10:
                        continue
                    else:
                        self.__cnc_raise_error(res)
                    
                # NCデータのRead終了を通知
                res = self.__dll.cnc_upend4(self.__handle)

                # EW_DATA (エラー詳細あり)
                if res == 5:
                    detail_err = self.__cnc_getdtailerr()
                    raise Exception(ew_data_errmap[detail_err])
                else:
                    self.__cnc_raise_error(res)
            except:
                res = self.__dll.cnc_upend4(self.__handle)
                self.__cnc_raise_error(res)

            return result

    def write_file(self, path, data):
        '''NCプログラムを書き込む。

        Args:
            path (str): 絶対パス
            data (bytes): 書き込むデータをバイナリで渡す。
        '''
        with self.__lock:
            self.__open()
            
            # ファイルが存在するなら一旦削除
            if self.exist_file(path):
                # ダミーPGを存在確認し、本来の消す対象の選択状態を先に外す
                self.exist_file('//CNC_MEM/USER/LIBRARY/O8999')
                self.delete_file(path)
            
            # EW_DATA(5): データの誤り の詳細エラー内容
            dwnstart4_errmap = {
                1 : 'フォルダ名の誤り。'}
            download4_errmap = {
                1 : 'NCデータ内の構文の誤り。',
                2 : 'TVチェック有効の時、ブロック内の文字数(ブロック末尾のLFを含む)が奇数のブロックが検出された。',
                3 : 'NC指令プログラムの登録本数がオーバーしている。',
                4 : '同一のプログラム番号が既に登録されている。',
                5 : '同一のプログラム番号がNC側で選択されている。'}

            # 返り値と引数定義
            self.__dll.cnc_dwnstart4.restype = c_short
            self.__dll.cnc_dwnstart4.argtypes = (c_ushort, c_short, c_char_p)
            self.__dll.cnc_download4.restype = c_short
            self.__dll.cnc_download4.argtypes = (c_ushort, POINTER(c_long), c_char_p)
            self.__dll.cnc_dwnend4.restype = c_short
            self.__dll.cnc_dwnend4.argtypes = (c_ushort,)

            try:
                # CNC側にNCプログラムのWrite開始を要求
                data_type = c_short(0) # 0: NC指令プログラム
                dir_name_p = c_char_p(create_string_buffer(bytes('//CNC_MEM/USER/LIBRARY/', 'utf-8')).raw) # Writeするディレクトリ名
                res = self.__dll.cnc_dwnstart4(self.__handle, data_type, dir_name_p)
                
                # EW_DATA (エラー詳細あり)
                if res == 5:
                    detail_err = self.__cnc_getdtailerr()
                    raise Exception(dwnstart4_errmap[detail_err])
                else:
                    self.__cnc_raise_error(res)
                
                # Writeするデータを整形し、1024ごとに配列に格納
                format_data = b'\n' + data + b'\n%' # データ全体の先頭には'LF'を、末尾には'LF%'を付加
                splited_data = [format_data[i:i+1024] for i in range(0, len(format_data), 1024)] # 1024ごとに分割

                count = 0
                while True:
                    # NCデータのWriteを行う
                    data_p = c_char_p(create_string_buffer(splited_data[count]).raw)
                    length = c_long(1024)
                    res = self.__dll.cnc_download4(self.__handle, byref(length), data_p)
                    
                    # EW_OK（正常完了）
                    if res == 0:
                        # Writeしたデータに末文字があれば終了
                        if data_p.value[-1:] == b'%':
                            break
                        else:
                            count += 1
                    # EW_DATA (エラー詳細あり)
                    elif res == 5:
                        detail_err = self.__cnc_getdtailerr()
                        raise Exception(download4_errmap[detail_err])
                    # EW_BUFFER（バッファがフル状態なのでリトライ）
                    elif res == 10:
                        continue
                    else:
                        self.__cnc_raise_error(res)
                
                # NCデータのWrite終了を通知
                res = self.__dll.cnc_dwnend4(self.__handle)
                
                # EW_DATA (エラー詳細あり)
                if res == 5:
                    detail_err = self.__cnc_getdtailerr()
                    raise Exception(download4_errmap[detail_err])
                else:
                    self.__cnc_raise_error(res)

            except:
                res = self.__dll.cnc_dwnend4(self.__handle)
                self.__cnc_raise_error(res)

    def delete_file(self, path):
        '''NCプログラムを削除する。

        注意：現在は、加工PGのみ削除可能。
        
        Args:
            path (str): 絶対パス
        '''
        filenm = path.split('/')[-1]
        if filenm[0:1] != 'O':
            raise Exception('加工PGのみ削除可能。')
        with self.__lock:
            self.__open()

            # ダミーPGを存在確認し、本来の消す対象の選択状態を先に外す
            self.exist_file('//CNC_MEM/USER/LIBRARY/O8999')
            
            # 返り値と引数定義
            self.__dll.cnc_delete.restype = c_short
            self.__dll.cnc_delete.argtypes = (c_ushort, c_short)

            # ファイルの削除を行う
            res = self.__dll.cnc_delete(self.__handle, c_short(int(filenm[1:])))
            if res == 5:
                pass # 'プログラム(number)が見つかりません。'はスキップ
            else:
                self.__cnc_raise_error(res)

    def __cnc_saveprog_start(self):
        '''(未テスト)高速プログラム管理でプログラム保存する。

        加工プログラムは CNC 装置内部の不揮発性メモリに記憶されています。
        加工プログラムが格納される不揮発性メモリには書き込み回数の制限があります。
        上位のパソコンから加工の都度自動的に加工プログラムをダウンロードする使い方など、
        加工プログラムの登録・削除を頻繁に繰り返すような使い方の場合には、
        必ず「高速プログラム管理cnc_saveprog_start/cnc_saveprog_end」をご使用下さい。
        「高速プログラム管理cnc_saveprog_start/cnc_saveprog_end」では、
        プログラムの登録・変更・削除時に不揮発性メモリへの保存が行われません。
        '''
        with self.__lock:
            self.__open()
            # 返り値と引数定義
            self.__dll.cnc_saveprog_start.restype = c_short
            self.__dll.cnc_saveprog_start.argtypes = (c_ushort,)
            res = self.__dll.cnc_saveprog_start(self.__handle)
            self.__cnc_raise_error(res)

            if res == 13:
                self.__cnc_saveprog_end()
            else:
                self.__cnc_raise_error(res)

    def __cnc_saveprog_end(self):
        '''(未テスト)高速プログラム管理が有効（NCパラメータHPM(No.11354#7)=1）の場合、
        本関数によりプログラムの保存が可能となります。
        '''
        with self.__lock:
            self.__open()
            # 返り値と引数定義
            self.__dll.cnc_saveprog_end.restype = c_short
            self.__dll.cnc_saveprog_end.argtypes = (c_ushort, POINTER(c_short))

            while True:
                result_p = c_short(1024)
                res = self.__dll.cnc_saveprog_end(self.__handle, byref(result_p))
                # EW_BUSY (BYSYなら再試行)
                if res == -1:
                    continue
                else:
                    self.__cnc_raise_error(res)
                # 結果
                self.__cnc_raise_error(result_p.value)

    # --- NCディレクトリ操作関連 --

    class IDBPDFADIR(Structure):
        '''フォルダの設定値を渡す構造体'''
        _fields_ = [
            ('path', c_char * 212), # パス名文字列（ドライブ名＋フォルダ名＋NULL終端）
            ('req_num', c_short), # 要求エントリ番号（何番目のフォルダ／ファイルの情報が欲しいかを）
            ('size_kind', c_short), # サイズの出力形式（0: ページ, 1: Byte, 2: KByte, 3: MByte）
            ('type', c_short), # プログラム一覧の形式（0: サイズ、コメント、加工時間スタンプを取得しない。1: 取得する。 ）
            ('dummy', c_short)] 

    class ODBPDFADIR(Structure):
        '''フォルダの一覧情報を返す構造体'''
        _fields_ = [
            ('data_kind', c_short), # データの種別（0:フォルダ, 1:ファイル）
            ('year', c_short), # 最終編集日時、以下同じ
            ('mon', c_short),
            ('day', c_short),
            ('hour', c_short),
            ('min', c_short),
            ('sec', c_short),
            ('dummy', c_short),
            ('dummy2', c_long),
            ('size', c_long), # サイズ
            ('attr', c_ulong), # ファイル／フォルダの属性
            ('d_f', c_char * 36), # ファイル／フォルダ名文字列
            ('comment', c_char * 52), # コメント
            ('o_time', c_char * 12)] # 加工時間スタンプ

    def find_dir(self, path):
        '''(未テスト)パス名を指定してファイルを検索する。

        Args:
            path (str): ディレクトリパス exp) //CNC_MEM/
        Return:
            list: 検索結果のリスト。中身は辞書データで1件ごとのデータを管理。
                  exp) [{ 'type': 'file', 'name': '100', 'size': '19', 'comment': 'BY IKEHARA' }, ...]
        '''
        with self.__lock:
            self.__open()
            result = []

            num_prog_p = c_short(2) # 読み取るプログラムの最大個数を設定。ポインタなので、実際に読み取った際のプログラム個数が設定される
            path_bytes = create_string_buffer(bytes(path, 'utf-8')).raw

            # 返り値と引数定義
            pdf_adir_in = J3.IDBPDFADIR() # フォルダの設定値
            pdf_adir_in.path = path_bytes # パス名文字列
            pdf_adir_in.req_num = c_short(0) # 要求エントリ番号。0始まりで、1ずつインクリメントする。
            pdf_adir_in.size_kind = 1 # byte表示
            pdf_adir_in.type = 1 # サイズ、コメント、加工時間スタンプを取得
            pdf_adir_out = J3.ODBPDFADIR() # フォルダの一覧情報

            self.__dll.cnc_rdpdf_alldir.restype = c_short
            self.__dll.cnc_rdpdf_alldir.argtypes = (c_ushort, POINTER(c_short), POINTER(J3.IDBPDFADIR), POINTER(J3.ODBPDFADIR))
            while True:
                res = self.__dll.cnc_rdpdf_alldir(self.__handle, byref(num_prog_p), byref(pdf_adir_in), byref(pdf_adir_out))
                self.__cnc_raise_error(res)

                # 実際に読み取ったプログラムの数が0なら即終了
                if num_prog_p.value == 0:
                    break

                data = {
                    'type': 'folder' if pdf_adir_out.data_kind == 0 else 'file',
                    'name': pdf_adir_out.d_f.decode(),
                    'size': str(pdf_adir_out.size),
                    'comment': pdf_adir_out.comment.decode()
                }
                result.append(data)
                # 最後の1ファイルを読み込んだら終了
                if num_prog_p.value <= 1:
                    break
                else:
                    pdf_adir_in.req_num += 1
            return result

    # --- NCデバイス操作関連 ---

    class IODBPMC(Structure):
        '''PMCデータを読み取り/書き込み時にデータを格納する構造体'''

        class U(Union):
            '''IODBPMC構造体の中で共用体として利用する'''
            _fields_ = [
                ('cdata', c_char),
                ('idata', c_short),
                ('ldata', c_long)]
        
        _anonymous_ = ('u',) # この設定で、iodbpmc.cdata のようにアクセス可能。また、iodbpmc.u.cdata よりも高速。
        _fields_ = [
            ('type_a', c_short),
            ('type_d', c_short),
            ('datano_s', c_ushort),
            ('datano_e', c_ushort),
            ('u', U)]

    def read_dev(self, dev, size=1):
        '''デバイス読み出し。
        
        Args:
            dev (str): デバイス番号 exp) R900 or R900.1 or D5600
            size (int): 読み取るデータのサイズ(byte) exp) 1 or 2 or 4
        Return:
            int: 読み出したデータの値を返す。但しオフセット有りの場合は、ビット（0 or 1）を返す。
        '''
        with self.__lock:
            self.__open()

            iodbpmc = J3.IODBPMC()
            devno = ''
            offset = -1

            # オフセット有りの場合、オフセット値を取得
            if dev.find('.') != -1:
                devno = dev[0:dev.find('.')]
                offset = int(dev[dev.find('.')+1:])
                if offset > 7 or 0 > offset:
                    raise Exception('書き込むデバイスのオフセット値が不正です。0~7の範囲内で指定してください。')
            # オフセット無し
            else:
                devno = dev
            
            type_a = 0
            type_d = 0
            add_index = 0
            add_length = 0

            # デバイス名設定
            if dev[0] == 'R':
                type_a = 5
            elif dev[0] == 'D':
                type_a = 9
            else:
                raise Exception('R、またはDデバイスを設定して下さい。')

            # サイズごとの動的設定
            if size == 1:
                type_d = 0
                add_index = 0
                add_length = 1
            elif size == 2:
                type_d = 1
                add_index = 1
                add_length = 2
            elif size == 4:
                type_d = 2
                add_index = 3
                add_length = 4
            else:
                raise Exception('サイズは、1(byte) or 2(byte) or 4(byte)のどれかを設定して下さい。')

            # read処理とエラーチェック
            self.__dll.pmc_rdpmcrng.restype = c_short
            self.__dll.pmc_rdpmcrng.argtypes = (c_ushort, c_short, c_short, c_ushort, c_ushort, c_ushort, POINTER(J3.IODBPMC))
            res = self.__dll.pmc_rdpmcrng(
                self.__handle,
                c_short(type_a), # 5=R(内部リレー), 9=D(データテーブル)
                c_short(type_d), # 0=バイト型, 1=ワード型, 2=ロング型
                c_ushort(int(devno[1:])), # 開始するPMCアドレス番号
                c_ushort(int(devno[1:]) + add_index), # 終了するPMCアドレス番号
                8 + add_length, # data_type = 0(バイト型):8+N, 1(ワード型):8+(N*2), 2(ロング型):8+(N*4) ※但しNは読み取るデータの個数
                byref(iodbpmc))
            self.__pmc_raise_error(res)

            # readした値を取得
            data = None
            if dev[0] == 'R':
                data = iodbpmc.cdata[0]
            elif dev[0] == 'D':
                if size == 1:
                    data = int.from_bytes(iodbpmc.cdata, 'big')
                elif size == 2:
                    data = iodbpmc.idata
                elif size == 4:
                    data = iodbpmc.ldata
            
            # オフセット指定ならマスク処理
            if offset != -1:
                if data & self.__offset_dict[offset] != 0:
                    return 1
                else:
                    return 0
            else:
                return data

    def write_dev(self, dev, in_data, size=1):
        '''デバイス書き込み。
        
        Args:
            dev (str): デバイス番号 exp) R900 or R900.1 or D5600
            in_data (int): 書き込む値。但し、オフセット無しの場合は、0~255の範囲（8bit）、オフセット有りの場合は、0or1(1bit)。
            size (int): 読み取るデータのサイズ(byte) exp) 1 or 2 or 4
        '''
        with self.__lock:
            self.__open()
            
            iodbpmc = J3.IODBPMC()
            devno = ''
            offset = -1
            data = -1

            # オフセット有りの場合、オフセット値と書き込む値を取得
            if dev.find('.') != -1:
                if not (in_data == 1 or in_data == 0):
                    raise Exception('書き込むデータの値が不正です。オフセット有りの場合、0 or 1で指定してください。')

                devno = dev[0:dev.find('.')]
                offset = int(dev[dev.find('.')+1:])

                if offset > 7 or 0 > offset:
                    raise Exception('書き込むデバイスのオフセット値が不正です。0~7の範囲内で指定してください。')

                # 指定したオフセットだけの書き込みができないため、一度デバイスの値を読み込み、書き込む値を更新する。
                val = self.read_dev(devno)
                if in_data == 1 and val & self.__offset_dict[offset] == 0:
                    data = val + self.__offset_dict[offset]
                elif in_data == 0 and val & self.__offset_dict[offset] != 0:
                    data = val - self.__offset_dict[offset]
                else:
                    data = val
            # オフセット無し
            else:
                devno = dev
                data = in_data
            
            type_a = 0 
            type_d = 0
            add_index = 0
            add_length = 0

            # デバイス名設定
            if devno[0] == 'R':
                type_a = 5
            elif devno[0] == 'D':
                type_a = 9
            else:
                raise Exception('R、またはDデバイスを設定して下さい。')

            # サイズごとの動的設定
            if size == 1:
                iodbpmc.cdata = data
                type_d = 0
                add_index = 0
                add_length = 1
            elif size == 2:
                iodbpmc.idata = data
                type_d = 1
                add_index = 1
                add_length = 2
            elif size == 4:
                iodbpmc.ldata = data
                type_d = 2
                add_index = 3
                add_length = 4
            else:
                raise Exception('サイズは、1(byte) or 2(byte) or 4(byte)のどれかを設定して下さい。')

            # write設定
            iodbpmc.type_a = c_short(type_a)
            iodbpmc.type_d = c_short(type_d)
            iodbpmc.datano_s = c_ushort(int(devno[1:]))
            iodbpmc.datano_e = c_ushort(int(devno[1:]) + add_index)

            # write処理とエラーチェック
            self.__dll.pmc_wrpmcrng.restype = c_short
            self.__dll.pmc_wrpmcrng.argtypes = (c_ushort, c_short, POINTER(J3.IODBPMC))
            res = self.__dll.pmc_wrpmcrng(self.__handle, 8 + add_length, byref(iodbpmc))
            self.__pmc_raise_error(res)

    # --- エラー出力関連 ---

    def __cnc_raise_error(self, errcd):
        '''エラーコードから、エラーの内容をExceptionとして返す。
        エラーがない場合（errcd=0）は何もしない。

        Raises:
            Exception: エラーメッセージ
        '''
        __cnc_errmap = {
            -17 : '[EW_PROTOCOL] イーサネットボードからのデータが間違っています。',
            -16 : '[EW_SOCKET] CNCの電源、イーサネットケーブル、I/Fボードを調べてください。',
            -15 : '[EW_NODLL] 指定されたノードに対応する各CNCシリーズのDLLファイルがありません。',
            -8 : '[EW_HANDLE] ハンドル番号の誤り。正常なライブラリハンドル番号を取得する。',
            -7 : '[EW_VERSION] CNC/PMCのバージョンは、ライブラリのものと一致しません。',
            -6 : '[EW_UNEXP] 異常な状態のライブラリ。予期しないエラーが発生しました。',
            -2 : '[EW_RESET] RESETまたはSTOPボタンが押されました。',
            -1 : '[EW_BUSY] CNC処理が完了するまで待つか、再試行してください。',
            0 : '[EW_OK] 正常終了。',
            1 : '[EW_FUNC] 関数が実行されていない、または利用できません。',
            2 : '[EW_LENGTH] データブロック長の誤り、データの数のエラー',
            3 : '[EW_NUMBER] データ番号の誤り',
            4 : '[EW_ATTRIB] データ属性の誤り',
            5 : '[EW_DATA] 指定されたプログラムが見つかりません。',
            6 : '[EW_NOOPT] 該当するCNCオプションがありません。',
            7 : '[EW_PROT] 書き込み動作が禁止されています。',
            8 : '[EW_OVRFLOW] CNCテープメモリがオーバーフローしています。',
            9 : '[EW_PARAM] CNCパラメータが正しく設定されていません。',
            10 : '[EW_BUFFER] バッファが空またはいっぱいです。CNC処理が完了するまで待つか、再試行してください。',
            11 : '[EW_PATH] パス番号が正しくありません。',
            12 : '[EW_MODE] CNCモードが正しくありません。',
            13 : '[EW_REJECT] CNCの実行が拒否されます。実行の状態を確認してください。',
            14 : '[EW_DTSRVR] 一部のエラーは、データ・サーバで発生します。',
            15 : '[EW_ALARM] CNCのアラームにより機能を実行できません。アラームの原因を取り除いてください。',
            16 : '[EW_STOP] CNCのステータスが停止または緊急事態です。',
            17 : '[EW_PASSWD] CNCデータ保護機能によって保護されています。'}

        # EW_OK：正常
        if errcd == 0:
            return
        # EW_SOCKET：無効となったライブラリハンドルでライブラリ関数を実行すると、完了ステータスがEW_SOCKETに
        elif errcd == -16:
            self.close()
        raise Exception('Error (errcd: ' + str(errcd) + ') ' + __cnc_errmap.get(errcd, 'Unkown error'))

    def __pmc_raise_error(self, errcd):
        '''エラーコードから、エラーの内容をExceptionとして返す。
        エラーがない場合（errcd=0）は何もしない。

        ToDo: エラーコード-16と-17はのイーサネットのエラーは、更に詳細なエラーを表示可能。
              必要であれば今後取得するようにする。
              詳細は、https://www.inventcom.net/fanuc-focas-library/General/errcode

        Raises:
            Exception: エラーメッセージ
        '''
        __pmc_errmap = {
            -17 : '[EW_PROTOCOL] イーサネットボードからのデータが間違っています。',
            -16 : '[EW_SOCKET] CNCの電源、イーサネットケーブル、I/Fボードを調べてください。',
            -15 : '[EW_NODLL] 指定されたノードに対応する各CNCシリーズのDLLファイルがありません。',
            -8 : '[EW_HANDLE] ハンドル番号の誤り。正常なライブラリハンドル番号を取得する。',
            -7 : '[EW_VERSION] CNC/PMCのバージョンは、ライブラリのものと一致しません。',
            -6 : '[EW_UNEXP] 異常な状態のライブラリ。予期しないエラーが発生しました。',
            0 : '[EW_OK] 正常終了。',
            1 : '[EW_NOPMC] PMCは存在しません。',
            2 : '[EW_LENGTH] データブロック長の誤り',
            3 : '[EW_RANGE] アドレス範囲エラー',
            4 : '[EW_TYPE] アドレス型/データ型エラー',
            5 : '[EW_DATA] データエラー',
            6 : '[EW_NOOPT] 該当するCNCオプションはありません。',
            10 : '[EW_BUFFER] バッファが空またはいっぱいです。PMC処理が完了するまで待つか、再試行してください。',
            17 : '[EW_PASSWD] データは、CNCデータ保護機能によって保護されています。'}

        # EW_OK：正常
        if errcd == 0:
            return
        raise Exception('Error (errcd: ' + str(errcd) + ') ' + __pmc_errmap.get(errcd, 'Unkown error'))

    def __cnc_getdtailerr(self):
        '''CNC関数実行時に、発生したエラーの詳細情報を取得する為のステータス番号を返す。
        そのステータス番号がどのような意味を持つかは、エラーが発生したメソッドによって変わる。
        
        Return:
            int: 詳細エラー番号を返す。
        '''
        class ODBERR(Structure):
            _fields_ = [
                ('err_no', c_short), # 詳細ステータス 
                ('err_dtno', c_short)] # エラーデータ番号
        
        odberr = ODBERR()
        self.__dll.cnc_getdtailerr.restype = c_short
        self.__dll.cnc_getdtailerr.argtypes = (c_ushort, POINTER(ODBERR))
        res = self.__dll.cnc_getdtailerr(self.__handle, byref(odberr))
        self.__cnc_raise_error(res)
        return odberr.err_no

    def __pmc_getdtailerr(self):
        '''PMC関数実行時に、発生したエラーの詳細情報を取得する為のステータス番号を返す。
        そのステータス番号がどのような意味を持つかは、エラーが発生したメソッドによって変わる。
        
        Return:
            int: 詳細エラー番号を返す。
        '''
        class ODBPMCERR(Structure):
            _fields_ = [
                ('err_no', c_short), # 詳細ステータス 
                ('err_dtno', c_short)] # エラーデータ番号
        
        odberr = ODBPMCERR()
        self.__dll.pmc_getdtailerr.restype = c_short
        self.__dll.pmc_getdtailerr.argtypes = (c_ushort, POINTER(ODBPMCERR))
        res = self.__dll.pmc_getdtailerr(self.__handle, byref(odberr))
        self.__pmc_raise_error(res)
        return odberr.err_no
