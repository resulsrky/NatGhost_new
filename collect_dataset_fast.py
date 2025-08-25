# Dosya Adı: collect_dataset_ultra_fast.py

import time
import json
import random
import stun
import threading
import socket
from queue import Queue, Empty  # 'Empty' istisnasını buradan alıyoruz
from tqdm import tqdm

# --- PERFORMANS AYARLARI ---
NUM_WORKERS = 100
PACKET_TARGET = 100
OUTPUT_FILENAME = f"nat_dataset_ultra_fast_{int(time.time())}.json"

STUN_HOSTNAMES = [
    ('stun3.l.google.com', 19302)
]


# --- DÜZELTİLMİŞ WORKER (İŞÇİ) FONKSİYONU ---
def worker(task_queue, results_list, pbar):
    """Kuyruktan görevleri alır, STUN sorgusunu yapar ve sonucu listeye ekler."""
    while True:
        try:
            # Kuyruktan bir görev al. Kuyruk boşsa 'Empty' hatası fırlatır.
            server_ip, server_port = task_queue.get_nowait()
        except Empty:
            # Kuyrukta iş kalmadıysa, bu thread görevini bitirmiştir.
            break

        try:
            timestamp_before_send = int(time.time() * 1_000_000)

            # STUN sorgusunu gerçekleştir
            nat_type, public_ip, assigned_port = stun.get_ip_info(
                stun_host=server_ip,
                stun_port=server_port,
                source_port=0
            )

            data_point = {
                'inputs': {
                    'timestamp_us': timestamp_before_send,
                    'target_ip': server_ip,
                    'target_port': server_port
                },
                'outputs': {
                    'public_ip': public_ip,
                    'assigned_port': assigned_port
                }
            }
            results_list.append(data_point)
        except (stun.StunError, socket.gaierror, OSError):
            # STUN sorgusu başarısız olursa bu görevi atla
            pass
        finally:
            # İlerleme çubuğunu her görev denemesinden sonra güncelle
            pbar.update(1)
            # Kuyruğa görevin tamamlandığını bildir. Bu .join() için gereklidir.
            task_queue.task_done()


# --- ANA ÇALIŞTIRMA BLOĞU ---
# (Bu kısım hiç değişmedi)
if __name__ == "__main__":
    print("--- NatGhost Ultra Hızlı Veri Toplama Aracı (Düzeltilmiş) ---")

    print("STUN sunucu IP adresleri çözümleniyor...")
    resolved_servers = []
    for host, port in STUN_HOSTNAMES:
        try:
            ip = socket.gethostbyname(host)
            resolved_servers.append((ip, port))
            print(f"  -> {host} -> {ip}")
        except socket.gaierror:
            print(f"  -> UYARI: {host} adresi çözümlenemedi, atlanıyor.")

    if not resolved_servers:
        print("HATA: Hiçbir STUN sunucusu çözümlenemedi.")
        exit()

    print(f"\n{NUM_WORKERS} işçi ile {PACKET_TARGET} paket toplanacak...")

    start_time = time.time()

    task_queue = Queue()
    results_list = []

    for _ in range(PACKET_TARGET):
        server_ip, server_port = random.choice(resolved_servers)
        task_queue.put((server_ip, server_port))

    pbar = tqdm(total=PACKET_TARGET, desc="Veri Toplanıyor", unit="pkt")

    threads = []
    for _ in range(NUM_WORKERS):
        t = threading.Thread(target=worker, args=(task_queue, results_list, pbar))
        t.start()
        threads.append(t)

    # Kuyruktaki tüm işler bitene kadar bekle
    task_queue.join()

    # Thread'lerin tamamen sonlandığından emin olmak için bekle
    for t in threads:
        t.join()

    pbar.close()
    end_time = time.time()

    total_time = end_time - start_time
    packets_per_second = len(results_list) / total_time if total_time > 0 else 0

    print("\nVeri toplama tamamlandı. Sonuçlar dosyaya kaydediliyor...")
    with open(OUTPUT_FILENAME, 'w') as f:
        json.dump(results_list, f, indent=2)

    print("\n" + "=" * 50)
    print("İŞLEM BAŞARIYLA TAMAMLANDI!")
    print(f"-> Toplam Süre: {total_time:.2f} saniye")
    print(f"-> Toplanan Veri Noktası: {len(results_list)}")
    print(f"-> Ortalama Hız: {packets_per_second:.2f} paket/saniye")
    print(f"-> Çıktı Dosyası: '{OUTPUT_FILENAME}'")