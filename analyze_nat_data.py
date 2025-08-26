# Dosya Adı: analyze_nat_data.py

import json
import sys
import numpy as np
import matplotlib.pyplot as plt


def analyze_dataset(filename):
    """
    Toplanan NAT veri setini analiz eder ve istatistikleri gösterir.
    """
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"HATA: '{filename}' dosyası bulunamadı.")
        return
    except json.JSONDecodeError:
        print(f"HATA: '{filename}' dosyası geçerli bir JSON formatında değil.")
        return

    if not data:
        print("UYARI: Veri seti boş. Hiçbir başarılı paket kaydedilmemiş.")
        return

    # Tüm atanmış portları listede topla
    assigned_ports = [entry['outputs']['assigned_port'] for entry in data]

    if not assigned_ports:
        print("Veri setinde hiç 'assigned_port' bulunamadı.")
        return

    unique_ports = sorted(list(set(assigned_ports)))

    # Temel İstatistikler
    min_port = min(assigned_ports)
    max_port = max(assigned_ports)
    avg_port = np.mean(assigned_ports)
    std_dev = np.std(assigned_ports)

    print("\n" + "=" * 50)
    print("NAT Davranış Analizi Sonuçları")
    print("=" * 50)
    print(f"-> Analiz Edilen Dosya: {filename}")
    print(f"-> Toplam Veri Noktası: {len(assigned_ports)}")
    print(f"-> Benzersiz Port Sayısı: {len(unique_ports)}")
    print("-" * 50)
    print(f"-> En Düşük Atanan Port: {min_port}")
    print(f"-> En Yüksek Atanan Port: {max_port}")
    print(f"-> Ortalama Port: {int(avg_port)}")
    print(f"-> Standart Sapma: {std_dev:.2f}")
    print("=" * 50)

    print("\nSONUÇ:")
    if len(unique_ports) == 1:
        print("-> NAT Tipi Tahmini: Static veya Full Cone NAT.")
        print(f"   (Sadece tek bir port kullanıldı: {min_port})")
    elif std_dev < (max_port - min_port) / 4:  # Sapma, aralığa göre darsa
        print("-> NAT Tipi Tahmini: Restricted Cone veya Port Restricted Cone.")
        print(f"   (Portlar büyük ihtimalle {min_port} - {max_port} aralığında sıralı veya yakın atanıyor)")
    else:
        print("-> NAT Tipi Tahmini: Symmetric NAT veya Kaotik Port Ataması.")
        print(f"   (Portlar {min_port} - {max_port} aralığında dağınık bir şekilde atanıyor)")

    # Port dağılımını görselleştiren bir histogram oluştur
    plt.figure(figsize=(12, 6))
    plt.hist(assigned_ports, bins=100, color='skyblue', edgecolor='black')
    plt.title(f'NAT Tarafından Atanan Portların Dağılımı ({min_port}-{max_port})')
    plt.xlabel('Port Numarası')
    plt.ylabel('Kullanım Sıklığı')
    plt.grid(True, linestyle='--', alpha=0.6)

    plot_filename = f"port_distribution_{filename.replace('.json', '.png')}"
    plt.savefig(plot_filename)
    print(f"\n-> Port dağılım grafiği '{plot_filename}' olarak kaydedildi.")
    plt.show()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Kullanım: python analyze_nat_data.py <veri_dosyasi.json>")
    else:
        analyze_dataset(sys.argv[1])