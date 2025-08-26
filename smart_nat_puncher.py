# Dosya Adı: smart_nat_puncher.py
# Açıklama: NAT davranışını analiz edip öğrenen ve bu bilgiyle hedefe yönelik
#           UDP delme işlemi yapan akıllı bir araç.

import time
import socket
import threading
import random
import struct
import json
import requests
from queue import Queue, Empty
from tqdm import tqdm
import numpy as np

# --- GEREKLİ KÜTÜPHANELER ---
# pip install pystun3 numpy tqdm requests
try:
    import stun
except ImportError:
    print("\n[HATA] 'pystun3' kütüphanesi bulunamadı. Lütfen 'pip install pystun3' komutuyla kurun.\n")
    exit()


# -----------------------------


class SmartNATPuncher:
    """
    NAT davranışını analiz edip öğrenerek hedefli delme işlemi yapan sınıf.
    Strateji:
    1. PROFILLE: Yüksek hızda STUN sorguları ile kendi NAT'ının port atama profilini çıkar.
    2. ANALİZ ET: Toplanan port verisinden en olası port aralığını (min/max) belirle.
    3. DELME İŞLEMİ YAP: Bu kesin aralığı kullanarak hedefe yönelik UDP burst saldırısı gerçekleştir.
    """

    # --- TEMEL AYARLAR ---
    CONFIG = {
        'PROFILING_PROBES': 500,  # Profilleme için yapılacak STUN sorgusu sayısı
        'PROFILING_WORKERS': 150,  # Profilleme sırasında aynı anda çalışacak thread sayısı
        'PUNCH_PACKET_COUNT': 300,  # Delme işlemi sırasında her porta gönderilecek paket sayısı
        'PUNCH_PORT_LIMIT': 2000,  # Analiz edilen aralıktan en fazla kaç porta saldırılacağı
        'STUN_HOST': 'stun.l.google.com',
        'STUN_PORT': 19302,
        'LISTEN_PORT': 5000,
        'LISTEN_TIMEOUT': 20
    }

    # ---------------------

    def __init__(self):
        self.local_ip = self._get_local_ip()
        self.public_ip = self._get_public_ip()
        self.stun_server_ip = self._resolve_stun_host()

    def _get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _get_public_ip(self):
        try:
            return requests.get('https://api.ipify.org', timeout=5).text
        except Exception:
            print("⚠️ Public IP 'ipify' üzerinden alınamadı, STUN ile öğrenilecek.")
            return None  # Profilleme sırasında öğrenilecek

    def _resolve_stun_host(self):
        try:
            return socket.gethostbyname(self.CONFIG['STUN_HOST'])
        except socket.gaierror:
            print(
                f"❌ HATA: STUN sunucusu '{self.CONFIG['STUN_HOST']}' çözümlenemedi. İnternet bağlantınızı kontrol edin.")
            return None

    def _profiling_worker(self, task_queue, results_list, pbar):
        """Kuyruktan görevleri alır, STUN sorgusunu yapar ve sonucu listeye ekler."""
        while True:
            try:
                task_queue.get_nowait()
            except Empty:
                break

            try:
                _, _, assigned_port = stun.get_ip_info(
                    stun_host=self.stun_server_ip,
                    stun_port=self.CONFIG['STUN_PORT'],
                    source_port=0
                )
                if assigned_port:
                    results_list.append(assigned_port)
            except (stun.StunError, socket.timeout, OSError):
                pass
            finally:
                pbar.update(1)
                task_queue.task_done()

    def profile_nat_behavior(self):
        """Adım 1: Yüksek hızda STUN sorguları ile NAT port atama davranışını profiller."""
        if not self.stun_server_ip:
            return None

        print(f"\n🔍 Adım 1: NAT Davranışı Profillemesi Başlatılıyor...")
        print(f"   {self.CONFIG['PROFILING_PROBES']} sorgu {self.CONFIG['PROFILING_WORKERS']} işçi ile gönderilecek.")

        task_queue = Queue()
        for _ in range(self.CONFIG['PROFILING_PROBES']):
            task_queue.put(1)

        collected_ports = []
        pbar = tqdm(total=self.CONFIG['PROFILING_PROBES'], desc="NAT Profilleniyor", unit="sorgu")

        threads = []
        for _ in range(self.CONFIG['PROFILING_WORKERS']):
            t = threading.Thread(target=self._profiling_worker, args=(task_queue, collected_ports, pbar))
            t.start()
            threads.append(t)

        task_queue.join()
        for t in threads:
            t.join()
        pbar.close()

        if not collected_ports:
            print("❌ Profilleme başarısız. STUN sunucusundan hiç yanıt alınamadı.")
            return None

        # Eğer başta public IP alınamadıysa, ilk başarılı yanıttan al
        if not self.public_ip:
            try:
                _, self.public_ip, _ = stun.get_ip_info(stun_host=self.stun_server_ip,
                                                        stun_port=self.CONFIG['STUN_PORT'])
            except:
                self.public_ip = "Bilinmiyor"

        print(f"✅ Profilleme Tamamlandı. {len(collected_ports)} başarılı yanıt toplandı.")
        return collected_ports

    def analyze_port_range(self, port_list):
        """Adım 2: Toplanan portları analiz ederek min/max aralığını bulur."""
        print("\n📊 Adım 2: Port Verisi Analiz Ediliyor...")

        min_port = int(np.min(port_list))
        max_port = int(np.max(port_list))
        unique_ports = len(set(port_list))

        print(f"   -> En Düşük Port: {min_port}")
        print(f"   -> En Yüksek Port: {max_port}")
        print(f"   -> Benzersiz Port Sayısı: {unique_ports}")
        print(f"   -> TESPİT EDİLEN PORT ARALIĞI: [{min_port} - {max_port}]")

        return min_port, max_port

    def _mass_burst_worker(self, target_ip, ports_to_punch):
        """Belirlenen portlara yoğun UDP paketi gönderir."""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        for _ in range(self.CONFIG['PUNCH_PACKET_COUNT']):
            for port in ports_to_punch:
                try:
                    s.sendto(b'PUNCH', (target_ip, port))
                except Exception:
                    pass
        s.close()

    def _listen_for_responses(self, result_queue):
        """Delme işlemi sırasında hedeften gelebilecek yanıtları dinler."""
        print(f"   👂 Yanıtlar {self.CONFIG['LISTEN_PORT']} portundan dinleniyor...")
        responses = []
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(1)
            sock.bind(('0.0.0.0', self.CONFIG['LISTEN_PORT']))

            start_time = time.time()
            while time.time() - start_time < self.CONFIG['LISTEN_TIMEOUT']:
                try:
                    data, addr = sock.recvfrom(1024)
                    if data:  # Gelen herhangi bir veri başarı sayılır
                        print(f"   📨 BAŞARILI YANIT GELDİ! -> Adres: {addr}")
                        responses.append(addr)
                except socket.timeout:
                    continue
            sock.close()
        except Exception as e:
            print(f"   ❌ Dinleme hatası: {e}")

        if responses:
            result_queue.put(list(set(responses)))

    def execute_targeted_punch(self, target_ip, min_port, max_port):
        """Adım 3: Analiz edilen port aralığına hedefe yönelik delme işlemi uygular."""
        print("\n💥 Adım 3: Hedefe Yönelik Delme İşlemi Başlatılıyor...")

        ports_to_punch = list(range(min_port, max_port + 1))
        random.shuffle(ports_to_punch)
        ports_to_punch = ports_to_punch[:self.CONFIG['PUNCH_PORT_LIMIT']]

        print(f"   -> Hedef: {target_ip}")
        print(f"   -> Saldırılacak Port Sayısı: {len(ports_to_punch)}")
        print(f"   -> Port Başına Paket: {self.CONFIG['PUNCH_PACKET_COUNT']}")

        result_queue = Queue()

        listen_thread = threading.Thread(target=self._listen_for_responses, args=(result_queue,))
        burst_thread = threading.Thread(target=self._mass_burst_worker, args=(target_ip, ports_to_punch))

        listen_thread.start()
        time.sleep(0.5)  # Dinleyicinin başlaması için kısa bir süre bekle
        burst_thread.start()

        burst_thread.join()
        listen_thread.join()

        try:
            return result_queue.get_nowait()
        except Empty:
            return None

    def run(self):
        """Tüm süreci yöneten ana fonksiyon."""
        print("=" * 60)
        print("🚀 Akıllı NAT Delme Aracı Başlatıldı 🚀")
        print(f"Yerel IP: {self.local_ip} | Genel IP: {self.public_ip or 'Bilinmiyor'}")
        print("=" * 60)

        target_input = input("Hedef IP veya Alan Adını Girin: ").strip()
        try:
            target_ip = socket.gethostbyname(target_input)
        except socket.gaierror:
            print(f"❌ HATA: '{target_input}' adresi çözümlenemedi.")
            return

        # Adım 1: Profilleme
        collected_ports = self.profile_nat_behavior()
        if not collected_ports:
            print("\nSüreç sonlandırıldı.")
            return

        # Adım 2: Analiz
        min_port, max_port = self.analyze_port_range(collected_ports)

        # Adım 3: Delme İşlemi
        results = self.execute_targeted_punch(target_ip, min_port, max_port)

        # Sonuç
        print("\n" + "=" * 60)
        print("✨ İŞLEM TAMAMLANDI ✨")
        if results:
            print(f"\n🎉🎉🎉 BAŞARILI! 🎉🎉🎉")
            print("Hedefle doğrudan iletişim kurulabilecek adres(ler) bulundu:")
            for addr in results:
                print(f" -> {addr[0]}:{addr[1]}")
        else:
            print("\n💥 maalesef yanıt alınamadı. Farklı ayarlarla tekrar deneyin.")
        print("=" * 60)


# --------------------------------------------------------------------------
# HEDEFIN ÇALIŞTIRMASI GEREKEN BASİT YANITLAYICI (RESPONDER)
# --------------------------------------------------------------------------
class SimpleResponder:
    def __init__(self, port=SmartNATPuncher.CONFIG['LISTEN_PORT']):
        self.port = port
        self.running = True

    def start(self):
        print(f"\n🔊 Basit Yanıtlayıcı (Responder) {self.port} portunda başlatıldı.")
        print("Diğer taraf delme işlemini başlattığında gelen paketlere yanıt verecek.")
        print("Durdurmak için CTRL+C tuşlarına basın.")

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(('0.0.0.0', self.port))
            sock.settimeout(1)

            while self.running:
                try:
                    data, addr = sock.recvfrom(1024)
                    if data:
                        # Gelen herhangi bir pakete, geldiği adrese yanıt gönder
                        sock.sendto(b"ACK_RESPONSE", addr)
                        print(f"   -> {addr} adresinden paket alındı, yanıt gönderildi.")
                except socket.timeout:
                    continue
                except KeyboardInterrupt:
                    self.running = False

            sock.close()
            print("\n🛑 Yanıtlayıcı durduruldu.")
        except Exception as e:
            print(f"❌ Yanıtlayıcı hatası: {e}")


# --- ANA ÇALIŞTIRMA BLOĞU ---
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "responder":
        # Yanıtlayıcı modunda çalıştır
        responder = SimpleResponder()
        responder.start()
    else:
        # Ana Delme Aracı modunda çalıştır
        puncher = SmartNATPuncher()
        puncher.run()