import numpy as np
import matplotlib.pyplot as plt
from scipy import stats, signal
# import entropy  # Bu satırı kaldırdık
import time
from datetime import datetime
import socket
import asyncio
import aiohttp
import json
from collections import defaultdict, Counter
import warnings

warnings.filterwarnings('ignore')


class GoogleSTUNAnalyzer:
    def __init__(self):
        self.stun_servers = [
            'stun.l.google.com:19302',

        ]
        self.collected_ports = []
        self.timestamps = []
        self.local_ips = []
        self.public_ips = []
        self.session = None

    # Manuel entropy hesaplamaları
    def shannon_entropy(self, data):
        """Shannon entropy hesaplar"""
        _, counts = np.unique(data, return_counts=True)
        probabilities = counts / len(data)
        return -np.sum(probabilities * np.log2(probabilities + 1e-10))

    def approximate_entropy(self, data, m=2, r=None):
        """Approximate entropy hesaplar"""
        if r is None:
            r = 0.2 * np.std(data)

        def _maxdist(xi, xj, m):
            return max([abs(ua - va) for ua, va in zip(xi, xj)])

        def _phi(m):
            patterns = np.array([data[i:i + m] for i in range(len(data) - m + 1)])
            C = np.zeros(len(patterns))

            for i in range(len(patterns)):
                template = patterns[i]
                for j in range(len(patterns)):
                    if _maxdist(template, patterns[j], m) <= r:
                        C[i] += 1

            phi = (1.0 / len(patterns)) * sum([np.log(c / len(patterns)) for c in C])
            return phi

        return _phi(m) - _phi(m + 1)

    def sample_entropy(self, data, m=2, r=None):
        """Sample entropy hesaplar"""
        if r is None:
            r = 0.2 * np.std(data)

        def _maxdist(xi, xj):
            return max([abs(ua - va) for ua, va in zip(xi, xj)])

        def _phi(m):
            patterns = np.array([data[i:i + m] for i in range(len(data) - m + 1)])
            matches = 0

            for i in range(len(patterns)):
                for j in range(i + 1, len(patterns)):
                    if _maxdist(patterns[i], patterns[j]) <= r:
                        matches += 1

            return matches

        A = _phi(m)
        B = _phi(m + 1)

        if A == 0 or B == 0:
            return 0

        return -np.log(B / A)

    async def query_stun_server(self, server_url, timeout=5):
        """Tek bir STUN sunucusuna sorgu atar"""
        try:
            # STUN sorgusu için özel bir implementasyon gerekebilir
            # Basitçe UDP bağlantısı yapalım
            server_host, server_port = server_url.split(':')
            server_port = int(server_port)

            # UDP socket ile STUN sorgusu
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)

            # Basit STUN binding request (RFC 5389)
            import os
            stun_request = b'\x00\x01\x00\x00\x21\x12\xa4\x42' + os.urandom(12)
            sock.sendto(stun_request, (server_host, server_port))

            response, addr = sock.recvfrom(1024)
            sock.close()

            # Response'tan port bilgisini çıkar
            if len(response) >= 20:
                # XOR-MAPPED-ADDRESS attribute'u için basit parsing
                if len(response) >= 28:
                    port_bytes = response[26:28]
                    mapped_port = (port_bytes[0] << 8) | port_bytes[1]
                    # XOR işlemi (STUN magic cookie ile)
                    mapped_port = mapped_port ^ 0x2112
                    return mapped_port, addr[0]

        except Exception as e:
            print(f"STUN sorgu hatası ({server_url}): {e}")
            return None, None

        return None, None

    async def mass_stun_query(self, num_queries=100, delay=0.1):
        """Çoklu STUN sorguları yapar"""
        print(f"Google STUN sunucularına {num_queries} sorgu gönderiliyor...")

        self.collected_ports = []
        self.timestamps = []
        self.public_ips = []

        query_count = 0

        for i in range(num_queries):
            for server in self.stun_servers:
                if query_count >= num_queries:
                    break

                start_time = time.time()
                port, public_ip = await self.query_stun_server(server)

                if port and public_ip:
                    self.collected_ports.append(port)
                    self.timestamps.append(start_time)
                    self.public_ips.append(public_ip)

                    print(f"Sorgu {query_count + 1:3d}: Port {port:5d} - {public_ip} - {server}")

                query_count += 1
                await asyncio.sleep(delay)

        print(f"\nToplam {len(self.collected_ports)} başarılı STUN sorgusu tamamlandı")
        return np.array(self.collected_ports), np.array(self.timestamps)

    def calculate_entropy_analysis(self, window_size=20):
        """Entropi analizi yapar"""
        if len(self.collected_ports) < window_size:
            print("Yeterli STUN verisi yok!")
            return None

        print("\n" + "=" * 60)
        print("GOOGLE STUN ENTROPİ ANALİZİ")
        print("=" * 60)

        entropies = {
            'shannon': [],
            'approximate': [],
            'sample': [],
        }

        # Pencere bazlı entropi hesapla
        for i in range(0, len(self.collected_ports) - window_size, window_size // 2):
            window = self.collected_ports[i:i + window_size]

            try:
                # Shannon entropisi
                shannon_ent = self.shannon_entropy(window)
                entropies['shannon'].append(shannon_ent)

                # Approximate entropy
                approx_ent = self.approximate_entropy(window)
                entropies['approximate'].append(approx_ent)

                # Sample entropy
                sample_ent = self.sample_entropy(window)
                entropies['sample'].append(sample_ent)

            except Exception as e:
                continue

        if not entropies['shannon']:
            print("Entropi hesaplanamadı!")
            return None

        # Gauss modeli fitting
        mu, sigma = stats.norm.fit(self.collected_ports)

        # Entropi grafiği
        plt.figure(figsize=(18, 15))

        # 1. Port dağılımı zaman serisi
        plt.subplot(4, 2, 1)
        time_deltas = [t - self.timestamps[0] for t in self.timestamps]
        plt.plot(time_deltas, self.collected_ports, 'bo-', alpha=0.7, markersize=4)
        plt.title('Google STUN - Zamana Göre Atanan Portlar')
        plt.xlabel('Zaman (s)')
        plt.ylabel('Port Numarası')
        plt.grid(True)

        # 2. Entropi değerleri
        plt.subplot(4, 2, 2)
        x_vals = range(len(entropies['shannon']))
        plt.plot(x_vals, entropies['shannon'], 'r-', label='Shannon Entropi', linewidth=2)
        plt.plot(x_vals, entropies['approximate'], 'g--', label='Approximate Entropi', alpha=0.7)
        plt.plot(x_vals, entropies['sample'], 'b:', label='Sample Entropi', alpha=0.7)
        plt.title('Entropi Metrikleri (Pencere Bazlı)')
        plt.xlabel('Pencere Index')
        plt.ylabel('Entropi Değeri')
        plt.legend()
        plt.grid(True)

        # 3. Port Dağılımı (KDE vs Gauss)
        plt.subplot(4, 2, (3, 4))
        x = np.linspace(min(self.collected_ports), max(self.collected_ports), 1000)

        # Histogram
        hist, bins, _ = plt.hist(self.collected_ports, bins=30, density=True,
                                 alpha=0.6, color='lightblue', label='Gerçek Veri Dağılımı (Histogram)')

        # KDE
        kde = stats.gaussian_kde(self.collected_ports)
        plt.plot(x, kde(x), 'b-', label='Gerçek Dağılım Modeli (KDE)', linewidth=2)

        # Gauss modeli
        gauss_fit = stats.norm(mu, sigma)
        plt.plot(x, gauss_fit.pdf(x), 'r--', label=f'Basit Gauss Modeli (μ={mu:.0f}, σ={sigma:.0f})', linewidth=2)

        plt.title('Port Dağılımı (KDE vs. Gauss Karşılaştırması)')
        plt.xlabel('Atanan Port Numarası (Geçen Süre - Milisaniye)')
        plt.ylabel('Yoğunluk')
        plt.legend()
        plt.grid(True)

        # 4. Box Plot
        plt.subplot(4, 2, 5)
        plt.boxplot(self.collected_ports, vert=False)
        plt.title('Port Dağılım Kutusu')
        plt.xlabel('Port Numarası')
        plt.grid(True)

        # 5. Gauss Q-Q Plot
        plt.subplot(4, 2, 6)
        stats.probplot(self.collected_ports, dist="norm", plot=plt)
        plt.title('Gauss Q-Q Plot (Normallik Testi)')
        plt.grid(True)

        # 6. Prediction Zones (Gauss bazlı)
        plt.subplot(4, 2, 7)
        x_pred = np.linspace(min(self.collected_ports) - 5000, max(self.collected_ports) + 5000, 1000)

        # %68, %95, %99.7 güven aralıkları
        plt.fill_between(x_pred, 0, gauss_fit.pdf(x_pred), alpha=0.2, color='red', label='Gauss Tahmini')

        # 1 sigma (68%)
        sigma1_low, sigma1_high = mu - sigma, mu + sigma
        mask1 = (x_pred >= sigma1_low) & (x_pred <= sigma1_high)
        plt.fill_between(x_pred[mask1], 0, gauss_fit.pdf(x_pred[mask1]), alpha=0.5, color='green',
                         label='68% Güven (%1σ)')

        # 2 sigma (95%)
        sigma2_low, sigma2_high = mu - 2 * sigma, mu + 2 * sigma
        mask2 = (x_pred >= sigma2_low) & (x_pred <= sigma2_high) & (~mask1)
        plt.fill_between(x_pred[mask2], 0, gauss_fit.pdf(x_pred[mask2]), alpha=0.3, color='yellow',
                         label='95% Güven (%2σ)')

        plt.title('Gauss Tabanlı Port Tahmin Bölgeleri')
        plt.xlabel('Port Numarası')
        plt.ylabel('Olasılık Yoğunluğu')
        plt.legend()
        plt.grid(True)

        # 7. KDE vs Gauss Fark Analizi
        plt.subplot(4, 2, 8)
        kde_values = kde(x)
        gauss_values = gauss_fit.pdf(x)
        difference = kde_values - gauss_values

        plt.plot(x, difference, 'purple', linewidth=2, label='KDE - Gauss Farkı')
        plt.axhline(y=0, color='black', linestyle='--', alpha=0.5)
        plt.title('KDE vs Gauss Model Farkı')
        plt.xlabel('Port Numarası')
        plt.ylabel('Yoğunluk Farkı')
        plt.legend()
        plt.grid(True)

        plt.tight_layout()
        plt.savefig('google_stun_gauss_kde_analysis.png', dpi=300, bbox_inches='tight')
        plt.show()

        # İstatistikler
        print(f"Toplam Sorgu: {len(self.collected_ports)}")
        print(f"Port Aralığı: {min(self.collected_ports)} - {max(self.collected_ports)}")
        print(f"Port Ortalaması: {np.mean(self.collected_ports):.2f}")
        print(f"Port Std: {np.std(self.collected_ports):.2f}")

        print(f"\n🔍 GAUSS MODEL PARAMETRELERİ:")
        print(f"  μ (Ortalama): {mu:.2f}")
        print(f"  σ (Std Sapma): {sigma:.2f}")
        print(f"  68% Güven Aralığı: {mu - sigma:.0f} - {mu + sigma:.0f}")
        print(f"  95% Güven Aralığı: {mu - 2 * sigma:.0f} - {mu + 2 * sigma:.0f}")
        print(f"  99.7% Güven Aralığı: {mu - 3 * sigma:.0f} - {mu + 3 * sigma:.0f}")

        # Normallik testleri
        shapiro_stat, shapiro_p = stats.shapiro(
            self.collected_ports[:5000] if len(self.collected_ports) > 5000 else self.collected_ports)
        ks_stat, ks_p = stats.kstest(self.collected_ports, lambda x: stats.norm.cdf(x, mu, sigma))

        print(f"\n📊 NORMALLİK TESTLERİ:")
        print(f"  Shapiro-Wilk p-value: {shapiro_p:.6f}")
        print(f"  Kolmogorov-Smirnov p-value: {ks_p:.6f}")
        print(f"  Gauss uyumu: {'İyi' if ks_p > 0.05 else 'Zayıf'}")

        print(f"\nShannon Entropi Ortalaması: {np.mean(entropies['shannon']):.4f}")
        print(f"Approximate Entropi Ortalaması: {np.mean(entropies['approximate']):.4f}")

        return entropies, {'mu': mu, 'sigma': sigma, 'shapiro_p': shapiro_p, 'ks_p': ks_p}

    def analyze_nat_behavior(self):
        """NAT davranış analizi yapar"""
        if not self.collected_ports:
            print("STUN verisi yok!")
            return

        print("\n" + "=" * 60)
        print("NAT DAVRANIŞ ANALİZİ")
        print("=" * 60)

        # Port farkları
        diffs = np.diff(self.collected_ports)

        # NAT tipi analizi
        unique_public_ips = len(set(self.public_ips))
        port_changes = len(set(self.collected_ports))

        print(f"Farklı Public IP Sayısı: {unique_public_ips}")
        print(f"Farklı Port Sayısı: {port_changes}")
        print(f"Toplam Sorgu: {len(self.collected_ports)}")

        # NAT tipi tahmini
        if unique_public_ips > 1:
            print("🔍 NAT Tipi: Symmetric NAT (Farklı public IP'ler)")
        elif port_changes == len(self.collected_ports):
            print("🔍 NAT Tipi: Symmetric NAT (Her sorguda farklı port)")
        elif port_changes == 1:
            print("🔍 NAT Tipi: Full Cone NAT (Aynı port)")
        else:
            print("🔍 NAT Tipi: Restricted Cone/Port Restricted Cone")

        # Port allocation pattern
        unique_diffs = len(set(diffs))
        print(f"Farklı Port Farkları: {unique_diffs}")

        if unique_diffs == 1:
            print("📊 Port Atama Paterni: Sequential (Ardışık)")
        elif unique_diffs < 10:
            print("📊 Port Atama Paterni: Fixed Increment (Sabit artış)")
        else:
            print("📊 Port Atama Paterni: Random (Rastgele)")

        # Örüntü analizi
        self.detect_patterns(diffs)

    def detect_patterns(self, diffs):
        """Örüntü tespiti"""
        print("\n🔍 ÖRÜNTÜ ANALİZİ:")

        # En sık farklar
        diff_counter = Counter(diffs)
        common_diffs = diff_counter.most_common(5)

        print("En sık port farkları:")
        for diff, count in common_diffs:
            percentage = (count / len(diffs)) * 100
            print(f"  Fark {diff:6d}: {count:3d} kez ({percentage:.1f}%)")

        # Ardışık tekrarlar
        max_consecutive = 0
        current_consecutive = 1
        prev_diff = diffs[0] if len(diffs) > 0 else 0

        for diff in diffs[1:]:
            if diff == prev_diff:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 1
            prev_diff = diff

        print(f"Maksimum ardışık tekrar: {max_consecutive}")

        # İstatistikler
        if len(diffs) > 0:
            print(f"Fark ortalaması: {np.mean(diffs):.2f}")
            print(f"Fark std: {np.std(diffs):.2f}")

    def predict_next_ports(self, num_predictions=5):
        """Sonraki portları tahmin et (Gauss + KDE modelleri)"""
        if len(self.collected_ports) < 10:
            print("Tahmin için yeterli veri yok!")
            return

        print("\n" + "=" * 60)
        print("PORT TAHMİN DENEMESİ (GAUß + KDE)")
        print("=" * 60)

        last_ports = self.collected_ports[-10:]
        last_diffs = np.diff(last_ports)

        # Gauss modeli parametreleri
        mu, sigma = stats.norm.fit(self.collected_ports)

        # Basit tahmin modelleri
        predictions = {
            'average': [],
            'linear': [],
            'last_pattern': [],
            'gauss_mean': [],
            'gauss_1sigma': [],
            'gauss_2sigma': [],
            'kde_peak': []
        }

        # 1. Ortalama fark ile tahmin
        avg_diff = np.mean(last_diffs)
        last_port = last_ports[-1]

        for i in range(num_predictions):
            next_port = int(last_port + avg_diff)
            next_port = max(1024, min(65535, next_port))
            predictions['average'].append(next_port)
            last_port = next_port

        # 2. Lineer regresyon
        x = np.arange(len(last_ports))
        slope, intercept, _, _, _ = stats.linregress(x, last_ports)

        for i in range(1, num_predictions + 1):
            next_port = int(slope * (len(last_ports) + i) + intercept)
            next_port = max(1024, min(65535, next_port))
            predictions['linear'].append(next_port)

        # 3. Son pattern'i kullan
        common_diff = Counter(last_diffs).most_common(1)[0][0] if len(last_diffs) > 0 else 0
        last_port = last_ports[-1]

        for i in range(num_predictions):
            next_port = last_port + common_diff
            next_port = max(1024, min(65535, next_port))
            predictions['last_pattern'].append(next_port)
            last_port = next_port

        # 4. Gauss model tahminleri
        # Gaussian mean etrafında tahmin
        for i in range(num_predictions):
            # Gauss ortalamasına doğru yönelme tahmini
            trend_to_mean = int(mu + np.random.normal(0, sigma / 4))
            trend_to_mean = max(1024, min(65535, trend_to_mean))
            predictions['gauss_mean'].append(trend_to_mean)

        # 5. 1-sigma aralığından sampling
        for i in range(num_predictions):
            sigma1_sample = int(np.random.normal(mu, sigma))
            sigma1_sample = max(1024, min(65535, sigma1_sample))
            predictions['gauss_1sigma'].append(sigma1_sample)

        # 6. 2-sigma aralığından sampling
        for i in range(num_predictions):
            sigma2_sample = int(np.random.normal(mu, sigma / 2))  # Daha muhafazakar
            sigma2_sample = max(1024, min(65535, sigma2_sample))
            predictions['gauss_2sigma'].append(sigma2_sample)

        # 7. KDE peak detection
        kde = stats.gaussian_kde(self.collected_ports)
        x_range = np.linspace(min(self.collected_ports), max(self.collected_ports), 1000)
        kde_values = kde(x_range)

        # En yüksek yoğunluk noktasını bul
        peak_idx = np.argmax(kde_values)
        kde_peak = x_range[peak_idx]

        for i in range(num_predictions):
            # KDE peak'i etrafında küçük varyasyonlar
            kde_prediction = int(kde_peak + np.random.normal(0, sigma / 6))
            kde_prediction = max(1024, min(65535, kde_prediction))
            predictions['kde_peak'].append(kde_prediction)

        # Tahminleri göster
        print("📊 ÇOKLU MODEL TAHMİNLERİ:")
        print("-" * 50)

        print("🔹 Ortalama Fark Tahmini:")
        for i, port in enumerate(predictions['average'], 1):
            print(f"  Tahmin {i}: Port {port}")

        print("\n🔹 Lineer Regresyon Tahmini:")
        for i, port in enumerate(predictions['linear'], 1):
            print(f"  Tahmin {i}: Port {port}")

        print("\n🔹 Son Pattern Tahmini:")
        for i, port in enumerate(predictions['last_pattern'], 1):
            print(f"  Tahmin {i}: Port {port}")

        print(f"\n🎯 GAUß MODEL TAHMİNLERİ (μ={mu:.0f}, σ={sigma:.0f}):")
        print("🔹 Gauss Ortalama Yönelimli:")
        for i, port in enumerate(predictions['gauss_mean'], 1):
            print(f"  Tahmin {i}: Port {port}")

        print("\n🔹 Gauss 1-Sigma Sampling:")
        for i, port in enumerate(predictions['gauss_1sigma'], 1):
            print(f"  Tahmin {i}: Port {port}")

        print("\n🔹 Gauss 2-Sigma Konservatif:")
        for i, port in enumerate(predictions['gauss_2sigma'], 1):
            print(f"  Tahmin {i}: Port {port}")

        print(f"\n🔍 KDE Peak Tahmini (Peak: {kde_peak:.0f}):")
        for i, port in enumerate(predictions['kde_peak'], 1):
            print(f"  Tahmin {i}: Port {port}")

        # Masscan için optimal aralık önerisi
        print(f"\n🎯 MASSCAN OPTİMAL ARALIK ÖNERİSİ:")
        print(f"  🔹 Gauss 68% Güven: {int(mu - sigma)} - {int(mu + sigma)}")
        print(f"  🔹 Gauss 95% Güven: {int(mu - 2 * sigma)} - {int(mu + 2 * sigma)}")
        print(f"  🔹 KDE Peak ±σ/2: {int(kde_peak - sigma / 2)} - {int(kde_peak + sigma / 2)}")

        optimal_start = max(1024, int(min(mu - sigma, kde_peak - sigma / 2)))
        optimal_end = min(65535, int(max(mu + sigma, kde_peak + sigma / 2)))
        port_count = optimal_end - optimal_start + 1

        print(f"  🚀 Önerilen Tarama: {optimal_start} - {optimal_end} ({port_count} port)")
        print(f"  ⚡ 65k pps ile süre: ~{port_count / 65000:.2f} saniye")

        return predictions

    def generate_report(self):
        """Detaylı rapor oluşturur"""
        if not self.collected_ports:
            print("Rapor için veri yok!")
            return

        report = {
            'timestamp': datetime.now().isoformat(),
            'total_queries': len(self.collected_ports),
            'port_range': [int(min(self.collected_ports)), int(max(self.collected_ports))],
            'port_mean': float(np.mean(self.collected_ports)),
            'port_std': float(np.std(self.collected_ports)),
            'unique_public_ips': len(set(self.public_ips)),
            'unique_ports': len(set(self.collected_ports)),
            'stun_servers_used': list(set([s.split(':')[0] for s in self.stun_servers])),
            'estimated_nat_type': self.estimate_nat_type(),
            'common_port_diffs': dict(Counter(np.diff(self.collected_ports)).most_common(5)) if len(
                self.collected_ports) > 1 else {}
        }

        print("\n" + "=" * 60)
        print("DETAYLI ANALİZ RAPORU")
        print("=" * 60)

        for key, value in report.items():
            if key != 'common_port_diffs':
                print(f"{key:20s}: {value}")

        print("\nEn sık port farkları:")
        for diff, count in report['common_port_diffs'].items():
            print(f"  Fark {diff}: {count} kez")

        # Raporu dosyaya kaydet
        with open('google_stun_analysis_report.json', 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\nRapor 'google_stun_analysis_report.json' dosyasına kaydedildi.")

        return report

    def estimate_nat_type(self):
        """NAT tipini tahmin et"""
        unique_ips = len(set(self.public_ips))
        unique_ports = len(set(self.collected_ports))

        if unique_ips > 1:
            return "Symmetric NAT"
        elif unique_ports == len(self.collected_ports):
            return "Symmetric NAT"
        elif unique_ports == 1:
            return "Full Cone NAT"
        else:
            return "Restricted/Port Restricted Cone NAT"


async def main():
    analyzer = GoogleSTUNAnalyzer()

    try:
        # 1. Google STUN sunucularına sorgu at
        ports, timestamps = await analyzer.mass_stun_query(num_queries=200, delay=0.2)

        if len(ports) < 20:
            print("Yeterli veri toplanamadı! Daha fazla sorgu gerekli.")
            return

        # 2. Entropi analizi
        entropies = analyzer.calculate_entropy_analysis()

        # 3. NAT davranış analizi
        analyzer.analyze_nat_behavior()

        # 4. Port tahmini
        analyzer.predict_next_ports(num_predictions=5)

        # 5. Detaylı rapor
        analyzer.generate_report()

        print("\n" + "=" * 60)
        print("GOOGLE STUN ANALİZİ TAMAMLANDI")
        print("=" * 60)
        print("📋 Çıkarımlar:")
        print("  • NAT tipi belirlendi")
        print("  • Port atama paterni analiz edildi")
        print("  • Entropi değerleri hesaplandı")
        print("  • Sonraki port tahminleri yapıldı")

    except KeyboardInterrupt:
        print("\nAnaliz kullanıcı tarafından durduruldu.")
    except Exception as e:
        print(f"Analiz hatası: {e}")


if __name__ == "__main__":
    import os
    import sys

    print("Google STUN Sunucu Analizi")
    print("=" * 40)

    # Asyncio event loop çalıştır
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())