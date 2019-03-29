# coding: utf-8
'''
本テストはマキノJ3のFanucテストスクリプトです。

※注意　デバイスの操作によって、物理的な機械が動く可能性があります。
      必ず安全を確かめ、テストコード内の操作を理解した上で実行して下さい。

'''
import os
import sys
import unittest

from j3 import J3


class TestJ3(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        '''テストクラスが初期化される際に一度だけ呼ばれる。'''
        print('----- TestJ3 start ------')
        cls.j3 = J3.get_connection('192.168.48.*:8193')
        
    @classmethod
    def tearDownClass(cls):
        '''テストクラスが解放される際に一度だけ呼ばれる。'''
        cls.j3.close()
        print('----- TestJ3 end ------')

    def setUp(self):
        '''テストごとに開始前に必ず実行'''
        if not self.j3.is_open():
            self.skipTest('指定されたIPに接続できません。電源が入っていない可能性があります。')

    def test_d_dev_operation(self):
        '''Dデバイスの読み書きテスト。'''
        # first. 初期化しておく
        self.j3.write_dev('D11600', 0)
        self.j3.write_dev('D11601', 0)
        self.j3.write_dev('D11602', 0)
        self.j3.write_dev('D11603', 0)
        self.j3.write_dev('D11604', 0)
        self.assertEqual(self.j3.read_dev('D11600'), 0)
        self.assertEqual(self.j3.read_dev('D11601'), 0)
        self.assertEqual(self.j3.read_dev('D11602'), 0)
        self.assertEqual(self.j3.read_dev('D11603'), 0)
        self.assertEqual(self.j3.read_dev('D11604'), 0)
        # 1. D11600に1byteサイズで値を書き込み、D11601以降に影響がないかテスト
        self.j3.write_dev('D11600', 1)
        self.assertEqual(self.j3.read_dev('D11600'), 1)
        self.assertEqual(self.j3.read_dev('D11601'), 0)
        self.j3.write_dev('D11600', 255)
        self.assertEqual(self.j3.read_dev('D11600'), 255)
        self.assertEqual(self.j3.read_dev('D11601'), 0)
        # 2. D11600に1byteサイズより大きい値を書き込み、例外が出るかテスト
        with self.assertRaises(TypeError):
            self.j3.write_dev('D11600', 256)
        # 3. D11600に2byteサイズで値を書き込み、D11602以降に影響がないかテスト
        self.j3.write_dev('D11600', 256, size=2)
        self.assertEqual(self.j3.read_dev('D11600', size=2), 256)
        self.assertEqual(self.j3.read_dev('D11600'), 0)
        self.assertEqual(self.j3.read_dev('D11601'), 1)
        self.assertEqual(self.j3.read_dev('D11602'), 0)
        self.assertEqual(self.j3.read_dev('D11603'), 0)
        self.j3.write_dev('D11600', 1000, size=2)
        self.assertEqual(self.j3.read_dev('D11600', size=2), 1000)
        self.assertEqual(self.j3.read_dev('D11600'), 232)
        self.assertEqual(self.j3.read_dev('D11601'), 3)
        self.assertEqual(self.j3.read_dev('D11602'), 0)
        self.assertEqual(self.j3.read_dev('D11603'), 0)
        self.j3.write_dev('D11600', -10, size=2)
        self.assertEqual(self.j3.read_dev('D11600', size=2), -10)
        self.assertEqual(self.j3.read_dev('D11600'), 246)
        self.assertEqual(self.j3.read_dev('D11601'), 255)
        self.assertEqual(self.j3.read_dev('D11602'), 0)
        self.assertEqual(self.j3.read_dev('D11603'), 0)
        # 4. D11600に2byteサイズより大きい値を書き込み、例外が出るかテスト
        with self.assertRaises(TypeError):
            self.j3.write_dev('D11600', 65537)
        # 5. D11600に4byteサイズで値を書き込み、D11602以降に影響がないかテスト
        self.j3.write_dev('D11600', 65537, size=4)
        self.assertEqual(self.j3.read_dev('D11600', size=4), 65537)
        self.assertEqual(self.j3.read_dev('D11600'), 1)
        self.assertEqual(self.j3.read_dev('D11601'), 0)
        self.assertEqual(self.j3.read_dev('D11602'), 1)
        self.assertEqual(self.j3.read_dev('D11603'), 0)
        self.assertEqual(self.j3.read_dev('D11604'), 0)
        self.j3.write_dev('D11600', 16777472, size=4)
        self.assertEqual(self.j3.read_dev('D11600', size=4), 16777472)
        self.assertEqual(self.j3.read_dev('D11600'), 0)
        self.assertEqual(self.j3.read_dev('D11601'), 1)
        self.assertEqual(self.j3.read_dev('D11602'), 0)
        self.assertEqual(self.j3.read_dev('D11603'), 1)
        self.assertEqual(self.j3.read_dev('D11604'), 0)
        self.j3.write_dev('D11600', -10000, size=4)
        self.assertEqual(self.j3.read_dev('D11600', size=4), -10000)
        self.assertEqual(self.j3.read_dev('D11600'), 240)
        self.assertEqual(self.j3.read_dev('D11601'), 216)
        self.assertEqual(self.j3.read_dev('D11602'), 255)
        self.assertEqual(self.j3.read_dev('D11603'), 255)
        self.assertEqual(self.j3.read_dev('D11604'), 0)
        # 6. D11600に4byteサイズより大きい値を書き込み、例外が出るかテスト
        with self.assertRaises(TypeError):
            self.j3.write_dev('D11600', 4294967297)
        # lastly. 最後も初期化しておく
        self.j3.write_dev('D11600', 0)
        self.j3.write_dev('D11601', 0)
        self.j3.write_dev('D11602', 0)
        self.j3.write_dev('D11603', 0)
        self.j3.write_dev('D11604', 0)

    def test_r_dev_operation(self):
        '''Rデバイスの読み書きテスト。'''
        # first. 初期化しておく
        self.j3.write_dev('R6653', 0)
        self.assertEqual(self.j3.read_dev('R6653.0'), 0)
        self.assertEqual(self.j3.read_dev('R6653.1'), 0)
        self.assertEqual(self.j3.read_dev('R6653.2'), 0)
        self.assertEqual(self.j3.read_dev('R6653.3'), 0)
        self.assertEqual(self.j3.read_dev('R6653.4'), 0)
        self.assertEqual(self.j3.read_dev('R6653.5'), 0)
        self.assertEqual(self.j3.read_dev('R6653.6'), 0)
        self.assertEqual(self.j3.read_dev('R6653.7'), 0)
        self.assertEqual(self.j3.read_dev('R6653'), 0)
        # 1. R6653にオフセットで1bitを書き込み、他のオフセットに影響がないかテスト
        self.j3.write_dev('R6653.0',1)
        self.j3.write_dev('R6653.1',0)
        self.j3.write_dev('R6653.2',1)
        self.j3.write_dev('R6653.3',0)
        self.j3.write_dev('R6653.4',1)
        self.j3.write_dev('R6653.5',0)
        self.j3.write_dev('R6653.6',1)
        self.j3.write_dev('R6653.7',0)
        self.assertEqual(self.j3.read_dev('R6653.0'), 1)
        self.assertEqual(self.j3.read_dev('R6653.1'), 0)
        self.assertEqual(self.j3.read_dev('R6653.2'), 1)
        self.assertEqual(self.j3.read_dev('R6653.3'), 0)
        self.assertEqual(self.j3.read_dev('R6653.4'), 1)
        self.assertEqual(self.j3.read_dev('R6653.5'), 0)
        self.assertEqual(self.j3.read_dev('R6653.6'), 1)
        self.assertEqual(self.j3.read_dev('R6653.7'), 0)
        self.assertEqual(self.j3.read_dev('R6653'), 85)
        self.j3.write_dev('R6653.0',0)
        self.j3.write_dev('R6653.1',1)
        self.j3.write_dev('R6653.2',0)
        self.j3.write_dev('R6653.3',1)
        self.j3.write_dev('R6653.4',0)
        self.j3.write_dev('R6653.5',1)
        self.j3.write_dev('R6653.6',0)
        self.j3.write_dev('R6653.7',1)
        self.assertEqual(self.j3.read_dev('R6653.0'), 0)
        self.assertEqual(self.j3.read_dev('R6653.1'), 1)
        self.assertEqual(self.j3.read_dev('R6653.2'), 0)
        self.assertEqual(self.j3.read_dev('R6653.3'), 1)
        self.assertEqual(self.j3.read_dev('R6653.4'), 0)
        self.assertEqual(self.j3.read_dev('R6653.5'), 1)
        self.assertEqual(self.j3.read_dev('R6653.6'), 0)
        self.assertEqual(self.j3.read_dev('R6653.7'), 1)
        self.assertEqual(self.j3.read_dev('R6653'), 170)
        self.j3.write_dev('R6653.0',1)
        self.j3.write_dev('R6653.1',1)
        self.j3.write_dev('R6653.2',1)
        self.j3.write_dev('R6653.3',1)
        self.j3.write_dev('R6653.4',1)
        self.j3.write_dev('R6653.5',1)
        self.j3.write_dev('R6653.6',1)
        self.j3.write_dev('R6653.7',1)
        self.assertEqual(self.j3.read_dev('R6653.0'), 1)
        self.assertEqual(self.j3.read_dev('R6653.1'), 1)
        self.assertEqual(self.j3.read_dev('R6653.2'), 1)
        self.assertEqual(self.j3.read_dev('R6653.3'), 1)
        self.assertEqual(self.j3.read_dev('R6653.4'), 1)
        self.assertEqual(self.j3.read_dev('R6653.5'), 1)
        self.assertEqual(self.j3.read_dev('R6653.6'), 1)
        self.assertEqual(self.j3.read_dev('R6653.7'), 1)
        self.assertEqual(self.j3.read_dev('R6653'), 255)
        # 2. R6653に値を書き込み、オフセットと一致するかテスト
        self.j3.write_dev('R6653',240)
        self.assertEqual(self.j3.read_dev('R6653.0'), 0)
        self.assertEqual(self.j3.read_dev('R6653.1'), 0)
        self.assertEqual(self.j3.read_dev('R6653.2'), 0)
        self.assertEqual(self.j3.read_dev('R6653.3'), 0)
        self.assertEqual(self.j3.read_dev('R6653.4'), 1)
        self.assertEqual(self.j3.read_dev('R6653.5'), 1)
        self.assertEqual(self.j3.read_dev('R6653.6'), 1)
        self.assertEqual(self.j3.read_dev('R6653.7'), 1)
        self.assertEqual(self.j3.read_dev('R6653'), 240)
        # lastly. 最後も初期化しておく
        self.j3.write_dev('R6653', 0)

    def test_file_operation(self):
        '''加工ファイル操作テスト。'''
        # 1. ファイルの書き込み、存在確認、読み込み、削除を行う
        self.skipTest('不揮発性メモリのため、書き込みに回数制限があり、必要な時以外'\
            '(write_file, read_file, exist_file, delete_fileの変更時)はskip。')
        data = b'O8990\nG4 X10.\nM30\n%'
        self.j3.write_file('//CNC_MEM/USER/LIBRARY/O8990', data)
        self.assertEqual(self.j3.exist_file('//CNC_MEM/USER/LIBRARY/O8990'), True)
        self.assertEqual(self.j3.read_file('//CNC_MEM/USER/LIBRARY/O8990'), b'O8990\nG4X10. \nM30')
        self.j3.delete_file('//CNC_MEM/USER/LIBRARY/O8990')

    def test_dir_operation(self):
        '''ディレクトリ操作テスト。'''
        dir_list = self.j3.find_dir('//CNC_MEM/')
        self.assertIsInstance(dir_list, list)
        for info_map in dir_list:
            self.assertIsInstance(info_map, dict)
            self.assertTrue('type' in info_map)
            self.assertTrue('name' in info_map)
            self.assertTrue('size' in info_map)
            self.assertTrue('comment' in info_map)

if __name__ == '__main__':
    unittest.main()
