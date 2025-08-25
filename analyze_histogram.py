# Dosya Adı: analyze_histograms.py

import sys
import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import math


def analyze_and_plot_histograms(filename):
    """
    Veri setini yükler ve her bir hedef STUN sunucusu için atanan portların
    histogram dağılımını görselleştirir.
    """
    print(f"'{filename}' veri seti yükleniyor...")
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"HATA: '{filename}' dosyası bulunamadı. Lütfen dosya adını kontrol edin.")
        return
    except json.JSONDecodeError:
        print(f"HATA: '{filename}' geçerli bir JSON dosyası değil.")
        return

    if not data:
        print("Uyarı: Veri seti boş.")
        return

    print(f"{len(data)} adet veri noktası başarıyla yüklendi.")

    # Veriyi Pandas DataFrame'e dönüştür ve sütunları yeniden adlandır
    df = pd.json_normalize(data)
    df.rename(columns={
        'inputs.target_ip': 'target_ip',
        'outputs.assigned_port': 'assigned_port'
    }, inplace=True)

    # Analiz edilecek benzersiz sunucu IP'lerini bul
    unique_servers = df['target_ip'].unique()
    num_servers = len(unique_servers)
    if num_servers == 0:
        print("Veri setinde analiz edilecek sunucu bulunamadı.")
        return

    print(f"\nAnaliz edilecek {num_servers} benzersiz STUN sunucusu bulundu: {unique_servers.tolist()}")

    # Grafikler için bir ızgara (grid) oluştur
    # Izgara boyutunu sunucu sayısına göre otomatik ayarla
    cols = 2
    rows = math.ceil(num_servers / cols)

    # Grafiğin genel boyutunu ve stilini ayarla
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, axes = plt.subplots(rows, cols, figsize=(12, rows * 4), sharey=True)
    # Eğer tek bir satır veya sütun varsa axes'i 2D diziye çevir
    if rows == 1 and cols > 1:
        axes = [axes]
    if cols == 1 and rows > 1:
        axes = [[ax] for ax in axes]
    if rows == 1 and cols == 1:
        axes = [[axes]]

    fig.suptitle('Hedef STUN Sunucusuna Göre Atanan Portların Histogram Dağılımı', fontsize=16)

    # Her bir sunucu için histogram çiz
    for i, server_ip in enumerate(unique_servers):
        row_idx, col_idx = divmod(i, cols)
        ax = axes[row_idx][col_idx]

        # Sadece mevcut sunucuya ait verileri filtrele
        server_data = df[df['target_ip'] == server_ip]

        # Seaborn ile histogram ve yoğunluk grafiği (KDE) çiz
        sns.histplot(data=server_data, x='assigned_port', bins=50, ax=ax, kde=True)

        ax.set_title(f'Hedef: {server_ip}', fontsize=12)
        ax.set_xlabel('Atanan Port Aralığı')
        ax.set_ylabel('Sıklık (Frekans)')

    # Boş kalan subplot'ları gizle
    for i in range(num_servers, rows * cols):
        row_idx, col_idx = divmod(i, cols)
        fig.delaxes(axes[row_idx][col_idx])

    plt.tight_layout(rect=[0, 0.03, 1, 0.96])  # Ana başlığın sıkışmasını önle

    # Grafiği kaydet
    output_filename = 'nat_histograms_by_server.png'
    plt.savefig(output_filename, dpi=150)
    print(f"\nHistogram grafikleri başarıyla '{output_filename}' olarak kaydedildi.")
    plt.show()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Kullanım: python analyze_histograms.py <veri_dosyası.json>")
    else:
        analyze_and_plot_histograms(sys.argv[1])