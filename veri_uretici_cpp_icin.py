import time
import json
import random
import stun
import threading
import socket
from queue import Queue, Empty
from tqdm import tqdm
import posix_ipc
import mmap

# --- AYARLAR ---
PACKET_TARGET = 5000
NUM_WORKERS = 100
# Paylaşılan bellek için POSIX standardında bir isim (başında / olmalı)
SHARED_MEMORY_NAME = "/nat_ghost_shm"

# ... (worker fonksiyonu ve veri toplama mantığı öncekiyle aynı) ...
STUN_HOSTNAMES = [('stun.l.google.com', 19302), ('stun1.l.google.com', 19302)]


def worker(task_queue, results_list, pbar):
    while True:
        try:
            server_ip, server_port = task_queue.get_nowait()
        except Empty:
            break
        try:
            timestamp = int(time.time() * 1_000_000)
            _, _, port = stun.get_ip_info(stun_host=server_ip, stun_port=server_port, source_port=0)
            if port is not None:
                results_list.append({'timestamp_us': timestamp, 'assigned_port': port})
        except Exception:
            pass
        finally:
            pbar.update(1)
            task_queue.task_done()


if __name__ == "__main__":
    print("--- Python Üretici: Veriler Toplanıyor ---")
    # ... (Veri toplama kodunun tamamı öncekiyle aynı) ...
    resolved_servers = []
    for host, port in STUN_HOSTNAMES:
        try:
            resolved_servers.append((socket.gethostbyname(host), port))
        except socket.gaierror:
            pass
    task_queue, results_list = Queue(), []
    for _ in range(PACKET_TARGET): task_queue.put(random.choice(resolved_servers))
    pbar = tqdm(total=PACKET_TARGET, desc="Veri Toplanıyor", unit="pkt")
    threads = []
    for _ in range(NUM_WORKERS):
        t = threading.Thread(target=worker, args=(task_queue, results_list, pbar));
        t.start();
        threads.append(t)
    task_queue.join();
    [t.join() for t in threads];
    pbar.close()

    print(f"\n{len(results_list)} adet geçerli veri toplandı. Paylaşılan belleğe yazılıyor...")

    # --- C++ İÇİN PAYLAŞILAN BELLEĞE YAZMA ---

    # 1. Veriyi JSON formatına ve ardından byte dizisine çevir
    json_str = json.dumps(results_list)
    encoded_data = json_str.encode('utf-8')
    data_size = len(encoded_data)

    memory = None
    mapfile = None
    try:
        # 2. POSIX uyumlu bir paylaşılan bellek bloğu oluştur
        #    Eğer varsa diye önce unlink etmeye çalışmak sağlam bir yöntemdir.
        try:
            posix_ipc.unlink_shared_memory(SHARED_MEMORY_NAME)
        except posix_ipc.ExistentialError:
            pass  # Zaten yoksa sorun değil

        memory = posix_ipc.SharedMemory(SHARED_MEMORY_NAME, posix_ipc.O_CREAT, size=data_size)

        # 3. Belleği prosesin adres alanına haritala (map et)
        mapfile = mmap.mmap(memory.fd, memory.size)

        # 4. Veriyi haritalanmış belleğe yaz
        mapfile.write(encoded_data)

        print("\n" + "=" * 50)
        print("PYTHON ÜRETİCİ BAŞARILI!")
        print(f"-> Veri ({data_size} byte), '{SHARED_MEMORY_NAME}' adlı paylaşılan belleğe yazıldı.")
        print("-> Şimdi C++ tüketici programını çalıştırabilirsiniz.")
        print("=" * 50)

    except Exception as e:
        print(f"Bir hata oluştu: {e}")
    finally:
        # 5. Kaynakları serbest bırak (belleği silme!)
        if mapfile:
            mapfile.close()
        if memory:
            memory.close_fd()