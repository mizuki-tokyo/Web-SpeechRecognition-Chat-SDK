import numpy as np
import threading
from typing import Union, Optional, List


class NumPyRingBuffer:
    """
    スレッドセーフな NumPy 配列ベースのリングバッファ
    数値データの高速な一括処理に最適化されています。
    """
    
    def __init__(self, maxsize: int, dtype=np.float64):
        """
        Args:
            maxsize: バッファの最大サイズ
            dtype: numpy 配列のデータ型（デフォルト: np.float64）
        """
        if maxsize <= 0:
            raise ValueError("maxsize must be positive")
        
        self.maxsize = maxsize
        self.dtype = dtype
        self.buffer = np.zeros(maxsize, dtype=dtype)
        self.head = 0  # 次に書き込む位置
        self.tail = 0  # 次に読み込む位置
        self.count = 0  # 現在のデータ数
        #self.lock = threading.Lock()

    
    def put(self, item: Union[int, float]) -> None:
        """
        単一の要素をバッファに追加
        
        Args:
            item: 追加する数値
        """
        #with self.lock:
        self.buffer[self.head] = item
        self.head = (self.head + 1) % self.maxsize
        
        if self.count < self.maxsize:
            self.count += 1
        else:
            # バッファが満杯の場合、tail も進める（古いデータを上書き）
            self.tail = (self.tail + 1) % self.maxsize
    
    def put_bulk(self, data: Union[List, np.ndarray]) -> None:
        """
        複数の要素を一括でバッファに追加
        
        Args:
            data: 追加するデータの配列
        """
        #with self.lock:
        # 引数の data が dtype が一致する numpy 配列の場合、コピーは作られない
        data = np.asarray(data, dtype=self.dtype)
        n = len(data)
        
        if n == 0:
            return
        
        if n >= self.maxsize:
            # データがバッファサイズ以上の場合、最後の maxsize 個だけを保持
            self.buffer[:] = data[-self.maxsize:]
            self.head = 0
            self.tail = 0
            self.count = self.maxsize
        else:
            # リングバッファの境界をまたぐ場合の処理
            if self.head + n <= self.maxsize:
                # 境界をまたがない場合
                self.buffer[self.head:self.head + n] = data
            else:
                # 境界をまたぐ場合
                split = self.maxsize - self.head
                self.buffer[self.head:] = data[:split]
                self.buffer[:n - split] = data[split:]
                # TODO
            
            # head の更新
            self.head = (self.head + n) % self.maxsize
            
            # count と tail の更新
            if self.count + n <= self.maxsize:
                self.count += n
            else:
                # バッファがオーバーフローする場合
                overflow = (self.count + n) - self.maxsize
                self.tail = (self.tail + overflow) % self.maxsize
                self.count = self.maxsize

    
    def get(self) -> Optional[Union[int, float]]:
        """
        単一の要素をバッファから取得
        
        Returns:
            取得した数値。バッファが空の場合は None
        """
        #with self.lock:
        if self.count == 0:
            return None
        
        item = self.buffer[self.tail]
        self.tail = (self.tail + 1) % self.maxsize
        self.count -= 1
        return item
    
    def get_bulk(self, n: int) -> np.ndarray:
        """
        複数の要素を一括でバッファから取得
        
        Args:
            n: 取得する要素数
            
        Returns:
            取得したデータの numpy 配列
        """
        #with self.lock:
        if self.count == 0:
            return np.array([], dtype=self.dtype)
        
        # 実際に取得できる数は要求数と現在のデータ数の最小値
        actual_n = min(n, self.count)
        result = np.zeros(actual_n, dtype=self.dtype)
        
        if self.tail + actual_n <= self.maxsize:
            # 境界をまたがない場合
            result[:] = self.buffer[self.tail:self.tail + actual_n]
        else:
            # 境界をまたぐ場合
            split = self.maxsize - self.tail
            result[:split] = self.buffer[self.tail:]
            result[split:] = self.buffer[:actual_n - split]
        
        # tail と count の更新
        self.tail = (self.tail + actual_n) % self.maxsize
        self.count -= actual_n
        
        return result
    
    def peek(self, n: int = 1) -> np.ndarray:
        """
        データを削除せずに先頭から n 個の要素を取得
        
        Args:
            n: 取得する要素数
            
        Returns:
            先頭から n 個の要素の numpy 配列
        """
        #with self.lock:
        if self.count == 0:
            return np.array([], dtype=self.dtype)
        
        actual_n = min(n, self.count)
        result = np.zeros(actual_n, dtype=self.dtype)
        
        if self.tail + actual_n <= self.maxsize:
            result[:] = self.buffer[self.tail:self.tail + actual_n]
        else:
            split = self.maxsize - self.tail
            result[:split] = self.buffer[self.tail:]
            result[split:] = self.buffer[:actual_n - split]
        
        return result
    
    def get_all(self) -> np.ndarray:
        """
        バッファ内の全データを取得（削除せず）
        
        Returns:
            バッファ内の全データの numpy 配列
        """
        #with self.lock:
        if self.count == 0:
            return np.array([], dtype=self.dtype)
        
        result = np.zeros(self.count, dtype=self.dtype)
        
        if self.tail + self.count <= self.maxsize:
            result[:] = self.buffer[self.tail:self.tail + self.count]
        else:
            split = self.maxsize - self.tail
            result[:split] = self.buffer[self.tail:]
            result[split:] = self.buffer[:self.count - split]
        
        return result
    
    def clear(self) -> None:
        """バッファをクリア"""
        #with self.lock:
        self.head = 0
        self.tail = 0
        self.count = 0
    
    def size(self) -> int:
        """現在のデータ数を取得"""
        #with self.lock:
        return self.count
    
    def is_empty(self) -> bool:
        """バッファが空かどうかを判定"""
        #with self.lock:
        return self.count == 0
    
    def is_full(self) -> bool:
        """バッファが満杯かどうかを判定"""
        #with self.lock:
        return self.count == self.maxsize
    
    def capacity(self) -> int:
        """バッファの最大容量を取得"""
        return self.maxsize


# 使用例とテスト用のコード
if __name__ == "__main__":
    # 基本的な使用例
    # Basic usage example
    buffer = NumPyRingBuffer(maxsize=10, dtype=np.float64)
    
    # 単一要素の追加・取得
    # Adding and retrieving single elements
    buffer.put(1.0)
    buffer.put(2.0)
    print(f"Single retrieve: {buffer.get()}")  # 1.0
    
    # 一括追加・取得
    # Bulk adding and retrieving
    buffer.put_bulk([3, 4, 5, 6, 7])
    print(f"Bulk retrieve: {buffer.get_bulk(3)}")  # [2. 3. 4.]
    
    # 全データの確認
    # Viewing all data in the buffer
    print(f"All data: {buffer.get_all()}")  # [5. 6. 7.]
    
    # バッファ状態の確認
    # Checking buffer status
    print(f"Number of items: {buffer.size()}")
    print(f"Empty?: {buffer.is_empty()}")
    print(f"Full?: {buffer.is_full()}")
    
    # オーバーフローのテスト
    # Testing overflow behavior
    
    # 10 個を超えるデータを追加
    # add more items than capacity (10)
    buffer.put_bulk(list(range(15)))  
    # 最後の 10 個が保持される
    # only the last 10 items are retained
    print(f"オーバーフロー後: {buffer.get_all()}") 
