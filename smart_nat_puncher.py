# Dosya Adı: ultimate_nat_analyzer_fixed.py
# Açıklama: Bir NAT'ın davranışsal imzasını; istatistiksel dağılım, zaman serisi desenleri
#           ve yoğun entropi bölgeleri analiziyle ortaya çıkaran, profesyonel
#           bir ağ teşhis ve görselleştirme aracı. (ValueError Düzeltmesi Eklendi)

import time
import socket
import threading
import random
import math
from collections import Counter
import requests
from queue import Queue, Empty
from tqdm import tqdm
import numpy as np

try:
    import stun
    import matplotlib.pyplot as plt
    from scipy.stats import norm, mode
except ImportError as e:
    print(f"\n[HATA] Gerekli bir kütüphane bulunamadı: {e.name}")
    print("Lütfen 'pip install pystun3 numpy tqdm requests matplotlib scipy' komutuyla tüm kütüphaneleri kurun.\n")
    exit()


class UltimateNATAnalyzer:
    CONFIG = {
        'PROFILING_PROBES': 1500,
        'PROFILING_WORKERS': 250,
        'STUN_HOST': 'stun.l.google.com',
        'STUN_PORT': 19302,
        'ENTROPY_WINDOW_SIZE': 500,
        'ENTROPY_STEP_SIZE': 50,
    }

    def __init__(self):
        self.local_ip = self._get_local_ip()
        self.public_ip = self._get_public_ip()
        self.stun_server_ip = self._resolve_stun_host()

    def _get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80));
            ip = s.getsockname()[0];
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _get_public_ip(self):
        try:
            return requests.get('https://api.ipify.org', timeout=5).text
        except Exception:
            print("⚠️ Public IP 'ipify' üzerinden alınamadı, STUN ile öğrenilecek.");
            return None

    def _resolve_stun_host(self):
        try:
            return socket.gethostbyname(self.CONFIG['STUN_HOST'])
        except socket.gaierror:
            print(f"❌ HATA: STUN sunucusu '{self.CONFIG['STUN_HOST']}' çözümlenemedi.");
            return None

    def _profiling_worker(self, task_queue, results_list, pbar):
        while True:
            try:
                task_queue.get_nowait()
            except Empty:
                break
            try:
                _, _, assigned_port = stun.get_ip_info(stun_host=self.stun_server_ip,
                                                       stun_port=self.CONFIG['STUN_PORT'], source_port=0)
                if assigned_port: results_list.append({'port': assigned_port, 'time': time.time()})
            except (stun.StunError, socket.timeout, OSError):
                pass
            finally:
                pbar.update(1); task_queue.task_done()

    def profile_nat_behavior(self):
        if not self.stun_server_ip: return None
        print(f"\n🔍 Adım 1: NAT Davranışı Profillemesi Başlatılıyor...")
        task_queue, collected_data = Queue(), []
        for _ in range(self.CONFIG['PROFILING_PROBES']): task_queue.put(1)

        with tqdm(total=self.CONFIG['PROFILING_PROBES'], desc="NAT Profilleniyor", unit="sorgu") as pbar:
            threads = [threading.Thread(target=self._profiling_worker, args=(task_queue, collected_data, pbar)) for _ in
                       range(self.CONFIG['PROFILING_WORKERS'])]
            for t in threads: t.start()
            task_queue.join()
            for t in threads: t.join()

        if not collected_data:
            print("❌ Profilleme başarısız.");
            return None

        if not self.public_ip:
            try:
                _, self.public_ip, _ = stun.get_ip_info(stun_host=self.stun_server_ip,
                                                        stun_port=self.CONFIG['STUN_PORT'])
            except:
                self.public_ip = "Bilinmiyor"

        print(f"✅ Profilleme Tamamlandı. {len(collected_data)} başarılı yanıt toplandı.")
        collected_data.sort(key=lambda x: x['time'])
        return collected_data

    def _calculate_entropy(self, data):
        # HATA DÜZELTMESİ: NumPy array'inin boş olup olmadığı .size ile kontrol edilir.
        if data.size == 0: return 0
        counts = Counter(data)
        total_items = len(data)
        return -sum((count / total_items) * math.log2(count / total_items) for count in counts.values())

    def analyze_entropy_density(self, ports, window_size, step_size):
        min_p, max_p = ports.min(), ports.max()
        entropy_map = []

        for start_port in range(min_p, max_p - window_size + 1, step_size):
            end_port = start_port + window_size
            ports_in_window = ports[(ports >= start_port) & (ports < end_port)]

            # Burada len() kullanmak güvenlidir, ancak .size da kullanılabilir.
            if len(ports_in_window) > 10:
                entropy = self._calculate_entropy(ports_in_window)
                entropy_map.append({
                    'range': (start_port, end_port),
                    'entropy': entropy,
                    'hits': len(ports_in_window)
                })

        entropy_map.sort(key=lambda x: x['entropy'], reverse=True)
        return entropy_map

    def perform_ultimate_analysis(self, data_points):
        print("\n" + "=" * 80)
        print("📊 Adım 2: Nihai NAT Davranış Analizi Raporu")
        print("=" * 80)

        ports = np.array([dp['port'] for dp in data_points])

        min_port, max_port = int(ports.min()), int(ports.max())
        mean_port, std_dev = ports.mean(), ports.std()
        median_port, q1, q3 = np.percentile(ports, [50, 25, 75])
        unique_ports_ratio = len(np.unique(ports)) / len(ports)
        deltas = np.diff(ports)
        delta_mode_val, _ = mode(deltas) if len(deltas) > 0 else (0, 0)
        delta_std = deltas.std() if len(deltas) > 0 else 0

        print("\n--- A. Genel İstatistiksel Dağılım ---")
        print(f"Port Aralığı:             [{min_port} - {max_port}] (Genişlik: {max_port - min_port})")
        print(f"İstatistiksel Merkez:       Ortalama={int(mean_port)}, Medyan={int(median_port)}")
        print(f"Yayılım (IQR):            {int(q1)} - {int(q3)}")
        print(f"Benzersiz Port Oranı:     {unique_ports_ratio:.2%}")

        print("\n--- B. Sıralı Davranış Analizi (Desenler) ---")
        print(
            f"Adım Farkı (Delta) Modu:  {int(delta_mode_val[0]) if isinstance(delta_mode_val, np.ndarray) else int(delta_mode_val)} (en sık tekrarlanan port artış miktarı)")
        print(f"Adım Farkı (Delta) Std Sap: {delta_std:.2f} (Düşük değer > Sıralı, Yüksek değer > Rastgele)")

        print("\n--- C. Yoğun Entropi Bölgeleri (En Rastgele Aralıklar) ---")
        entropy_map = self.analyze_entropy_density(ports, self.CONFIG['ENTROPY_WINDOW_SIZE'],
                                                   self.CONFIG['ENTROPY_STEP_SIZE'])
        if not entropy_map:
            print("Yeterli veri yoğunluğu bulunamadığı için entropi bölgeleri hesaplanamadı.")
        else:
            print(f"Analiz, {self.CONFIG['ENTROPY_WINDOW_SIZE']} port genişliğindeki pencerelerle yapılmıştır.")
            for i, item in enumerate(entropy_map[:3]):
                print(
                    f" #{i + 1} En Yoğun Bölge: Port {item['range'][0]}-{item['range'][1]} | Entropi: {item['entropy']:.4f} bits | {item['hits']} isabet")
            print(
                "  -> Yorum: Bu bölgeler, NAT'ınızın en tahmin edilemez ve çeşitli port atamalarını yaptığı 'sıcak noktalardır'.")

        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(18, 20), gridspec_kw={'height_ratios': [2, 3, 2]})
        fig.suptitle('Nihai NAT Davranış Analizi Raporu', fontsize=22, y=0.97)

        ax1.hist(ports, bins=200, density=True, color='skyblue', edgecolor='k', alpha=0.7,
                 label='Gerçek Port Yoğunluğu (Gauss Analizi)')
        x_gauss = np.linspace(min_port, max_port, 1000)
        pdf_gauss = norm.pdf(x_gauss, loc=mean_port, scale=std_dev)
        ax1.plot(x_gauss, pdf_gauss, 'r--', linewidth=2, label=f'İdeal Gauss Dağılımı')
        ax1.set_title('Grafik 1 (NE?): Port Atama Dağılımı ve Gauss Karşılaştırması', fontsize=16)
        ax1.set_xlabel('Port Numarası');
        ax1.set_ylabel('Yoğunluk');
        ax1.legend();
        ax1.grid(True, alpha=0.5)

        ax2.plot(range(len(ports)), ports, marker='o', linestyle='-', markersize=2.5, alpha=0.6, color='green',
                 label='Port Atama Sırası')
        ax2.set_title('Grafik 2 (NASIL?): Portların İstek Sırasına Göre Atanma Deseni', fontsize=16)
        ax2.set_xlabel('İstek Sıra Numarası');
        ax2.set_ylabel('Atanan Port Numarası');
        ax2.legend();
        ax2.grid(True, alpha=0.5)

        if entropy_map:
            x_entropy = [item['range'][0] + self.CONFIG['ENTROPY_WINDOW_SIZE'] / 2 for item in entropy_map]
            y_entropy = [item['entropy'] for item in entropy_map]
            ax3.plot(x_entropy, y_entropy, marker='.', linestyle='-', color='darkorange', label='Bölgesel Entropi')
            peak_entropy = entropy_map[0]
            ax3.axvline(peak_entropy['range'][0] + self.CONFIG['ENTROPY_WINDOW_SIZE'] / 2, color='crimson',
                        linestyle='--', linewidth=2, label=f"Zirve Entropi: {peak_entropy['entropy']:.2f} bits")
            ax3.set_title('Grafik 3 (NEREDE?): Port Aralığındaki Rastgelelik (Entropi) Yoğunluğu', fontsize=16)
            ax3.set_xlabel('Port Aralığı Merkezi');
            ax3.set_ylabel('Shannon Entropisi (bits)');
            ax3.legend();
            ax3.grid(True, alpha=0.5)

        plt.tight_layout(rect=[0, 0, 1, 0.95])
        filename = f"ultimate_nat_analysis_{int(time.time())}.png"
        plt.savefig(filename)
        print(f"\n-> Nihai analiz raporu grafiği '{filename}' olarak kaydedildi.")

    def run(self):
        print("=" * 80)
        print("🚀 Nihai NAT Analiz Laboratuvarı Başlatıldı 🚀")
        print(f"Yerel IP: {self.local_ip} | Genel IP: {self.public_ip or 'Bilinmiyor'}")
        print("=" * 80)

        collected_data = self.profile_nat_behavior()
        if not collected_data:
            print("\nSüreç sonlandırıldı.");
            return

        self.perform_ultimate_analysis(collected_data)
        print("\nAnaliz tamamlandı.")


if __name__ == "__main__":
    analyzer = UltimateNATAnalyzer()
    analyzer.run()