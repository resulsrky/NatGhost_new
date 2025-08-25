# Dosya Adı: nat_ghost_peer.py
# Amaç: İstatistiksel Tahmin ve Daraltılmış Aralıkta Delik Açma stratejisini uygulayan P2P istemcisi.

import socket
import time
import numpy as np
import random
import threading

# --- AYARLAR ---
# Bu sunucu, sadece kendi NAT parmak izimizi çıkarmak için kullanılır.
# Halka açık bir STUN sunucusu veya kendi kontrolünüzdeki bir sunucu olabilir.
FINGERPRINT_SERVER_HOST = '34.118.95.148'  # Google'ın halka açık bir STUN sunucusu
FINGERPRINT_SERVER_PORT = 19302

# Test için kullanılacak paket ve deneme sayıları
FINGERPRINT_PACKET_COUNT = 30  # Parmak izi için gönderilecek paket sayısı
PUNCH_BURST_COUNT = 150  # Delik açmak için gönderilecek paket sayısı
LISTEN_TIMEOUT = 5  # Başarılı bağlantı için dinleme süresi (saniye)


def get_nat_fingerprint(server_host, server_port, packet_count):
    """
    Kendi NAT'ımızın o an kullandığı port aralığını (min/max) tespit eder.
    """
    print(f"[1] Kendi NAT parmak izi çıkarılıyor ({packet_count} paket gönderilecek)...")
    collected_ports = []

    for i in range(packet_count):
        # Her denemede yeni soket kullanarak Simetrik NAT davranışını tetikle
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(1.0)
            message = f"fingerprint:{i + 1}"
            try:
                # STUN sunucusu, portu response içinde göndermez, sadece yansıtır.
                # Bu yüzden burada sendto/recvfrom ile bir delik açıp portu yakalamaya çalışıyoruz.
                # Ancak daha basit bir yöntem için, sadece gönderim yapıp sunucunun loglarına bakmak
                # veya daha gelişmiş bir STUN client kütüphanesi kullanmak gerekir.
                # Şimdilik bu kısmı simüle edip rastgele bir aralık döndürelim.
                # GERÇEK BİR STUN KÜTÜPHANESİ (örn: pystun3) BU KISMI ÇOK DAHA DOĞRU YAPAR.

                # ---- SİMÜLASYON BAŞLANGICI ----
                # Önceki testlerimize dayanarak, NAT'ımızın genellikle 35000-60000 arası portlar
                # atadığını biliyoruz. Bu aralıkta rastgele portlar üretelim.
                # Gerçek implementasyonda bu kısım pystun3 ile değiştirilmelidir.
                port = random.randint(35000, 60000)
                collected_ports.append(port)
                # ---- SİMÜLASYON BİTİŞİ ----

                print(f"    Paket {i + 1}/{packet_count} gönderildi...", end='\r')
            except socket.timeout:
                pass
        time.sleep(0.05)

    if not collected_ports:
        print("\n    HATA: Sunucudan hiç cevap alınamadı. Port aralığı belirlenemedi.")
        return None

    fingerprint = {
        'min_port': np.min(collected_ports),
        'max_port': np.max(collected_ports)
    }
    print(f"\n[OK] NAT Parmak İzi: Min Port={fingerprint['min_port']}, Max Port={fingerprint['max_port']}")
    return fingerprint


def listen_for_peer(listen_port, stop_event):
    """
    Karşı taraftan gelen delik açma paketlerini dinleyen thread.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            # Belirli bir porta bağlanmak yerine, OS'un bir port seçmesine izin veriyoruz
            s.bind(('', 0))
            print(f"\n[INFO] Dinleme başlatıldı. Port: {s.getsockname()[1]}")
        except Exception as e:
            print(f"Dinleme hatası: {e}")
            return

        s.settimeout(1.0)
        while not stop_event.is_set():
            try:
                data, addr = s.recvfrom(1024)
                print(f"\n\n--- BAĞLANTI BAŞARILI! ---")
                print(f"    -> {addr} adresinden bir 'punch' paketi alındı!")
                print(f"    -> Gelen Mesaj: {data.decode('utf-8')}")
                stop_event.set()  # Diğer thread'leri durdur
                return
            except socket.timeout:
                continue


def execute_hole_punch(target_ip, port_range, burst_count, stop_event):
    """
    Belirlenen IP ve port aralığına rastgele paketler göndererek delik açar.
    """
    print(f"\n[3] İstatistiksel Delik Açma (Hole Punching) Başlatılıyor...")
    print(f"    -> Hedef: {target_ip}")
    print(f"    -> Port Aralığı: {port_range}")
    print(f"    -> Paket Sayısı: {burst_count}")

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        for i in range(burst_count):
            if stop_event.is_set():
                print("\n[INFO] Başarılı bağlantı tespit edildi, delik açma durduruluyor.")
                break

            random_port = random.randint(port_range[0], port_range[1])
            message = f"punch:{i + 1}"
            try:
                s.sendto(message.encode('utf-8'), (target_ip, random_port))
                print(f"    -> Punch denemesi: {target_ip}:{random_port}", end='\r')
                time.sleep(0.02)
            except Exception as e:
                print(f"Gönderim hatası: {e}")

    print(f"\n[OK] {burst_count} adet 'punch' paketi gönderildi.")


if __name__ == "__main__":
    # AŞAMA 1: Kendi NAT parmak izimizi çıkarıyoruz (Bu kısmı gerçek STUN ile değiştirmek gerekir)
    # Şimdilik kendi aralığımızı da simüle edelim.
    my_fingerprint = {'min_port': 35000, 'max_port': 45000}
    # my_fingerprint = get_nat_fingerprint(FINGERPRINT_SERVER_HOST, FINGERPRINT_SERVER_PORT, FINGERPRINT_PACKET_COUNT)

    if my_fingerprint:
        print("-" * 50)
        print("[2] Sinyal Sunucusu Simülasyonu:")
        print("    Gerçek bir uygulamada, aşağıdaki bilgiler sinyal sunucusu")
        print("    aracılığıyla karşı tarafa iletilir:")
        print(f"    -> Kendi Port Aralığım: {my_fingerprint['min_port']} - {my_fingerprint['max_port']}")

        # --- BU BİLGİLERİ KARŞI KULLANICIDAN ALMANIZ GEREKİYOR ---
        try:
            peer_public_ip = input("    -> Lütfen karşı kullanıcının genel IP adresini girin: ")
            peer_min_port = int(input(f"    -> Lütfen karşı kullanıcının MIN portunu girin: "))
            peer_max_port = int(input(f"    -> Lütfen karşı kullanıcının MAX portunu girin: "))
            peer_port_range = (peer_min_port, peer_max_port)
            print("-" * 50)
        except ValueError:
            print("    HATA: Geçersiz giriş. Program sonlandırılıyor.")
            exit()

        # Hem dinleme hem de gönderme işlemlerini aynı anda yapmak için threading kullanıyoruz.
        stop_event = threading.Event()

        # Arka planda dinlemeyi başlat
        listener_thread = threading.Thread(target=listen_for_peer, args=(0, stop_event))
        listener_thread.daemon = True  # Ana program bitince thread'in de bitmesini sağlar
        listener_thread.start()

        # Eş zamanlı olarak delik açma işlemini başlat
        # Karşı tarafın da tam bu anda aynı işlemi başlattığını varsayıyoruz.
        time.sleep(1)  # Dinleyicinin başlaması için kısa bir bekleme
        puncher_thread = threading.Thread(target=execute_hole_punch,
                                          args=(peer_public_ip, peer_port_range, PUNCH_BURST_COUNT, stop_event))
        puncher_thread.start()

        # Ana thread'in, bağlantı başarılı olana veya süre dolana kadar beklemesi
        puncher_thread.join(timeout=LISTEN_TIMEOUT)

        if not stop_event.is_set():
            print(f"\n--- BAĞLANTI BAŞARISIZ ---")
            print(f"    -> {LISTEN_TIMEOUT} saniye içinde karşı taraftan paket alınamadı.")
            stop_event.set()  # Tüm thread'leri durdur

        print("\nProgram tamamlandı.")