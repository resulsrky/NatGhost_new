import json
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import scipy.stats as stats
import argparse
from pathlib import Path


def compare_gaussian_analysis(file_path):
    """
    NAT veri setini analiz eder, zaman serisi grafiği çizer ve
    port dağılımını hem KDE hem de Gauss modeliyle karşılaştırır.
    """
    # --- 1. VERİ YÜKLEME VE HAZIRLAMA ---
    print(f"'{file_path}' dosyası okunuyor...")
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"HATA: '{file_path}' dosyası bulunamadı.")
        return
    except json.JSONDecodeError:
        print(f"HATA: '{file_path}' geçerli bir JSON dosyası değil.")
        return

    if not data or len(data) < 2:
        print("UYARI: Analiz için yeterli veri yok.")
        return

    try:
        sorted_data = sorted(data, key=lambda x: x['inputs']['timestamp_us'])

        timestamps_all = [item['inputs']['timestamp_us'] for item in sorted_data]
        assigned_ports_all = [item['outputs']['assigned_port'] for item in sorted_data]

        valid_indices = [i for i, port in enumerate(assigned_ports_all) if port is not None]

        if not valid_indices:
            print("HATA: Veri setinde geçerli hiçbir port numarası bulunamadı. Tüm veriler 'None'.")
            return

        timestamps = [timestamps_all[i] for i in valid_indices]
        assigned_ports = np.array([assigned_ports_all[i] for i in valid_indices])

        none_count = len(assigned_ports_all) - len(assigned_ports)
        if none_count > 0:
            print(f"UYARI: {none_count} adet geçersiz (None) port verisi bulundu ve analizden çıkarıldı.")

    except KeyError:
        print("HATA: JSON dosyasında beklenen anahtarlar bulunamadı.")
        return

    print(f"{len(assigned_ports)} adet geçerli veri noktası zaman sırasına göre dizildi.")

    # --- 2. İSTATİSTİKSEL HESAPLAMALAR ---
    mu = np.mean(assigned_ports)
    sigma = np.std(assigned_ports)

    port_differences = np.diff(assigned_ports)
    if len(port_differences) > 0:
        sequential_like_count = np.sum((port_differences > 0) & (port_differences <= 2))
        if sequential_like_count / len(port_differences) > 0.7:
            nat_behavior = "Sıralı (Sequential)"
        else:
            nat_behavior = "Rastgele (Random) veya Kümelenmiş (Clustered)"
    else:
        nat_behavior = "Tespit Edilemedi (Yetersiz Veri)"

    print("\n--- Analiz Sonuçları ---")
    print(f"  -> Ortalama Port (μ): {mu:.2f}")
    print(f"  -> Standart Sapma (σ): {sigma:.2f}")
    print(f"  -> Tahmin Edilen NAT Davranışı: {nat_behavior}")

    # --- 3. GÖRSELLEŞTİRME ---
    sns.set_theme(style="whitegrid")
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 12), sharex=True)
    fig.suptitle('NAT Port Analizi (Gauss ve KDE Karşılaştırması)', fontsize=20, weight='bold')

    # **************************************************************************
    # *** İSTEDİĞİNİZ ZAMAN SERİSİ GRAFİĞİ BU BÖLÜMDE OLUŞTURULUYOR (ÜST GRAFİK) ***
    # **************************************************************************
    time_elapsed_ms = (np.array(timestamps) - timestamps[0]) / 1000.0
    ax1.plot(time_elapsed_ms, assigned_ports, marker='o', linestyle='-', markersize=3, alpha=0.7)
    ax1.set_title('Zamana Göre Atanan Portlar', fontsize=14)
    ax1.set_ylabel('Atanan Port Numarası', fontsize=12)
    ax1.ticklabel_format(style='plain', axis='y')

    # --- ALTTAKİ GRAFİK: PORT DAĞILIMI ANALİZİ ---
    sns.histplot(x=assigned_ports, bins=75, ax=ax2, stat="density",
                 label='Gerçek Veri Dağılımı (Histogram)', color='skyblue', alpha=0.6)
    sns.kdeplot(x=assigned_ports, ax=ax2, color='blue', linewidth=2.5,
                label='Gerçek Dağılım Modeli (KDE)')
    x_gauss = np.linspace(mu - 4 * sigma, mu + 4 * sigma, 1000)
    pdf_gauss = stats.norm.pdf(x_gauss, mu, sigma)
    ax2.plot(x_gauss, pdf_gauss, color='red', linestyle='--', linewidth=2.5,
             label='Basit Gauss Modeli')
    ax2.set_title('Port Dağılımı (KDE vs. Gauss)', fontsize=14)
    ax2.set_xlabel('Atanan Port Numarası (Geçen Süre - Milisaniye)', fontsize=12)
    ax2.set_ylabel('Yoğunluk', fontsize=12)
    ax2.legend()

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    output_filename = f"analiz_gauss_karsilastirma_{Path(file_path).stem}.png"
    plt.savefig(output_filename)
    print(f"\nGrafik '{output_filename}' olarak başarıyla kaydedildi.")

    try:
        plt.show()
    except Exception as e:
        print(f"Grafik penceresi açılamadı: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Bir NAT veri seti JSON dosyasını analiz eder ve dağılımını Gauss/KDE ile karşılaştırır.",
        epilog="Kullanım: python <script_adı> nat_dataset...json"
    )
    parser.add_argument("filename", type=Path, help="Analiz edilecek JSON dosyası.")
    args = parser.parse_args()
    compare_gaussian_analysis(args.filename)