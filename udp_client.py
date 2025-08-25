# Dosya Adı: udp_client.py
# Amaç: Simetrik NAT'ın port atama desenini analiz etmek.

import socket
import time
import numpy as np
import matplotlib.pyplot as plt

# --- AYARLAR ---
SERVER_HOST = '127.0.0.1'  # Sunucu farklı bir makinedeyse, onun genel IP adresini yazın
SERVER_PORT = 12345
PACKET_COUNT = 150  # Analiz için paket sayısı (150 iyi bir değerdir)
INTERVAL = 0.05  # Paketler arası bekleme süresi (saniye)


# --- ANALİZ FONKSİYONLARI ---

def find_time_correlation(timestamps, ports):
    """
    Zaman damgası ve port numaraları arasındaki korelasyonu inceler.
    Hem dağılım grafiği hem de aradaki farkların (offset) histogramını çizer.
    """
    print("\n[Gelişmiş Zaman Korelasyon Analizi Başlatılıyor]")

    if len(timestamps) < 10:
        print("  -> Analiz için yeterli veri noktası yok.")
        return

    # Zaman damgalarını mikrosaniye cinsinden tam sayıya çevir
    timestamps_int = (timestamps * 1_000_000).astype(np.int64)
    MODULO_VAL = 256  # Son 8 biti karşılaştırmak için

    time_mod = timestamps_int % MODULO_VAL
    port_mod = ports % MODULO_VAL

    # 1. Dağılım Grafiği (Scatter Plot)
    plt.figure(figsize=(10, 10))
    plt.scatter(time_mod, port_mod, alpha=0.6, s=50)
    plt.title(f'Zaman Damgası vs. Port (Modulo {MODULO_VAL})', fontsize=16)
    plt.xlabel(f'Zaman Damgası (mikrosaniye) % {MODULO_VAL}', fontsize=12)
    plt.ylabel(f'Atanan Port % {MODULO_VAL}', fontsize=12)
    plt.grid(True)
    corr_plot_filename = 'nat_correlation_plot.png'
    plt.savefig(corr_plot_filename)
    print(f"  -> Dağılım grafiği '{corr_plot_filename}' adıyla kaydedildi.")

    # 2. Fark (Offset) Analizi ve Histogram
    # Modulo aritmetiğine göre (port - zaman) farkını hesapla
    delta_mod = (port_mod - time_mod + MODULO_VAL) % MODULO_VAL

    plt.figure(figsize=(12, 6))
    plt.hist(delta_mod, bins=256, alpha=0.75, range=(0, 255))
    plt.title('Port ve Zaman Arasındaki Farkların Dağılımı (Histogram)', fontsize=16)
    plt.xlabel(f'(Port % {MODULO_VAL} - Zaman % {MODULO_VAL}) Değeri', fontsize=12)
    plt.ylabel('Sıklık (Frequency)', fontsize=12)
    plt.grid(axis='y', alpha=0.75)
    hist_plot_filename = 'nat_histogram_plot.png'
    plt.savefig(hist_plot_filename)
    print(f"  -> Fark histogramı '{hist_plot_filename}' adıyla kaydedildi.")
    print("\n  -> YORUM: Eğer histogramda bir veya birkaç çubuk diğerlerinden çok daha")
    print("     uzunsa, bu sabit bir 'offset' ilişkisi olduğunu gösterir. Bu, aradığımız anahtar olabilir.")


def analyze_nat_behavior(data):
    """Toplanan veriyi analiz etmek için ana fonksiyon."""
    print("\n--- Desen Analizi Başlatılıyor ---")
    if len(data) < 2:
        print("Analiz için yeterli veri yok.")
        return
    timestamps = np.array([item[0] for item in data])
    ports = np.array([item[1] for item in data])

    # En önemli analiz olan zaman korelasyonunu çağır
    find_time_correlation(timestamps, ports)


# --- VERİ TOPLAMA BÖLÜMÜ ---
collected_data = []
print("Simetrik NAT Gelişmiş Analiz Testi başlatılıyor...")
print(f"{PACKET_COUNT} adet paket gönderilecek...")

# Her paket için yeni bir soket oluşturarak Simetrik NAT'ı tetikle
for i in range(PACKET_COUNT):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(1.0)
        message = f"ADV_TEST:{i + 1}"
        try:
            send_time = time.perf_counter()
            s.sendto(message.encode('utf-8'), (SERVER_HOST, SERVER_PORT))
            response, server_addr = s.recvfrom(1024)
            response_str = response.decode('utf-8')
            public_ip, public_port_str = response_str.split(':')
            public_port = int(public_port_str)
            collected_data.append((send_time, public_port))
            # Kullanıcıya ilerlemeyi göstermek için satırı güncelleyerek yazdır
            print(f"Paket {i + 1}/{PACKET_COUNT}: Atanan Port -> {public_port}   ", end='\r')
        except socket.timeout:
            # Zaman aşımını sessizce geçebilir veya loglayabiliriz
            pass  # print(f"Paket {i+1} zaman aşımına uğradı.")

    time.sleep(INTERVAL)

print("\n\n--- Veri Toplama Tamamlandı ---")
print(f"Toplam {len(collected_data)} adet geçerli veri noktası toplandı.")

# Toplanan verilerle analiz fonksiyonunu çağır
analyze_nat_behavior(collected_data)