import time
import socket
import threading
import random
import struct
import requests
from collections import defaultdict, Counter
import numpy as np


class PublicIPNATPuncher:
    def __init__(self):
        self.local_ip = self.get_local_ip()
        self.public_ip = self.get_public_ip()
        self.target_public_ip = None
        self.mapping_behavior = defaultdict(list)
        self.discovered_ports = set()

    def get_local_ip(self):
        """Local IP'yi al"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def get_public_ip(self):
        """Public IP'yi öğren"""
        try:
            response = requests.get('https://api.ipify.org', timeout=5)
            return response.text
        except:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                public_ip = s.getsockname()[0]
                s.close()
                return public_ip
            except:
                return "unknown"

    def get_target_public_ip(self, target_input):
        """Hedefin public IP'sini al (IP veya domain)"""
        try:
            # Eğer IP formatındaysa direkt kullan
            try:
                socket.inet_aton(target_input)
                return target_input
            except:
                # Domain ise çözümle
                return socket.gethostbyname(target_input)
        except:
            print("❌ Hedef IP çözümlenemedi")
            return None

    def analyze_public_nat_mapping(self, stun_servers=None, num_probes=300):
        """Public IP üzerinden NAT mapping davranışını analiz et"""
        if stun_servers is None:
            stun_servers = [
                ("stun.l.google.com", 19302),
                ("stun1.l.google.com", 19302),
                ("stun2.l.google.com", 19302),
                ("stun3.l.google.com", 19302),
                ("stun4.l.google.com", 19302),
                ("stun.voip.blackberry.com", 3478),
                ("stun.voipgate.com", 3478)
            ]

        print("🔍 Public NAT Mapping Analizi Başlatılıyor...")
        print(f"📍 Public IP: {self.public_ip}")
        print(f"📍 Local IP: {self.local_ip}")

        collected_mappings = []

        for i in range(num_probes):
            try:
                # Yeni UDP socket oluştur
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.bind(('0.0.0.0', 0))  # Random local port
                s.settimeout(2)

                # Rastgele STUN sunucusu seç
                stun_host, stun_port = random.choice(stun_servers)

                # STUN Binding Request gönder
                s.sendto(b'\x00\x01\x00\x00\x21\x12\xa4\x42', (stun_host, stun_port))
                response, addr = s.recvfrom(1024)

                if len(response) >= 20:
                    # MAPPED-ADDRESS attribute'ını parse et
                    mapped_port = struct.unpack('!H', response[26:28])[0]
                    collected_mappings.append(mapped_port)

                    if (i + 1) % 50 == 0:
                        print(f"   📊 {i + 1}/{num_probes} mapping collected")

                s.close()

            except Exception as e:
                continue

        print(f"✅ {len(collected_mappings)} mapping collected")
        return collected_mappings

    def detect_nat_type(self, mappings):
        """NAT tipini public mapping'lere göre tespit et"""
        if not mappings:
            return "Unknown", []

        unique_ports = list(set(mappings))
        port_diffs = np.diff(sorted(unique_ports))

        if len(unique_ports) > 1 and np.std(port_diffs) > 50:
            nat_type = "Symmetric"
        else:
            nat_type = "Cone"

        print(f"🎯 NAT Type: {nat_type}")
        print(f"📈 Port Range: {min(mappings)} - {max(mappings)}")

        return nat_type, unique_ports

    def predict_target_ports(self, own_mappings, target_public_ip, num_prediction=1000):
        """Hedefin portlarını kendi mapping'lerimize göre tahmin et"""
        print("🎯 Hedef Port Tahmini Yapılıyor...")

        # Kendi mapping pattern'ini analiz et
        own_ports = sorted(own_mappings)
        port_min = min(own_ports)
        port_max = max(own_ports)
        port_std = np.std(np.diff(own_ports))

        # Tahmin edilen port aralığı
        if port_std < 10:  # Sequential mapping
            predicted_range = list(range(port_min - 100, port_max + 101))
        else:  # Random mapping
            # Hedefin IP'sine göre deterministic port tahmini
            target_hash = abs(hash(target_public_ip)) % 10000
            base_port = 30000 + (target_hash % 20000)
            predicted_range = list(range(base_port - 500, base_port + 501))

        # Rastgele karıştır ve sınırla
        random.shuffle(predicted_range)
        return predicted_range[:num_prediction]

    def mass_public_burst(self, target_public_ip, ports_to_attack, packet_count=500):
        """Public IP'ye yoğun burst saldırısı"""
        print(f"💥 Public Burst Saldırısı: {target_public_ip}")
        print(f"   🎯 {len(ports_to_attack)} porta {packet_count} paket")

        # Socket pool oluştur
        socket_pool = []
        for i in raange(100):  # 100 socket
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(0.01)
                socket_pool.append(s)
            except:
                continue

        sent_packets = 0
        start_time = time.time()

        # Yoğun burst
        for i in range(packet_count):
            for port in ports_to_attack:
                try:
                    s = random.choice(socket_pool)
                    packet_data = f"PUBLIC_BURST_{self.public_ip}_{port}_{time.time()}".encode()
                    s.sendto(packet_data, (target_public_ip, port))
                    sent_packets += 1
                except:
                    continue

            if (i + 1) % 100 == 0:
                elapsed = time.time() - start_time
                rate = sent_packets / elapsed if elapsed > 0 else 0
                print(f"   ⚡ {i + 1}/{packet_count} - {rate:.0f} pkt/s")

        # Cleanup
        for s in socket_pool:
            s.close()

        duration = time.time() - start_time
        print(f"   ✅ {sent_packets} paket gönderildi, {duration:.2f}s")
        return sent_packets

    def listen_for_public_responses(self, listen_port=5000, timeout=20):
        """Public yanıtları dinle"""
        print(f"👂 Public Yanıtlar Dinleniyor: port {listen_port}")

        responses = []
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', listen_port))
        sock.settimeout(1)

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                data, addr = sock.recvfrom(1024)
                if b"PUBLIC_RESPONSE" in data or b"BURST_ACK" in data:
                    responses.append({
                        'source': addr,
                        'data': data.decode(),
                        'time': time.time()
                    })
                    print(f"   📨 Yanıt: {addr}")
            except socket.timeout:
                continue

        sock.close()
        return responses

    def automated_public_punch(self, target_input):
        """Tam otomatik public NAT delme"""
        print("=" * 60)
        print("🚀 PUBLIC IP NAT DELME - TAM OTOMATİK")
        print("=" * 60)

        # 1. Hedef Public IP'yi al
        self.target_public_ip = self.get_target_public_ip(target_input)
        if not self.target_public_ip:
            return None

        print(f"🎯 Hedef: {self.target_public_ip}")

        # 2. Kendi NAT mapping'lerini öğren
        own_mappings = self.analyze_public_nat_mapping(num_probes=200)
        if not own_mappings:
            print("❌ Mapping analizi başarısız")
            return None

        # 3. NAT tipini belirle
        nat_type, unique_ports = self.detect_nat_type(own_mappings)

        # 4. Hedef portları tahmin et
        target_ports = self.predict_target_ports(own_mappings, self.target_public_ip, 800)
        print(f"🎯 {len(target_ports)} port hedeflenecek")

        # 5. Eşzamanlı burst ve dinleme
        burst_thread = threading.Thread(
            target=self.mass_public_burst,
            args=(self.target_public_ip, target_ports, 500)
        )

        listen_thread = threading.Thread(
            target=self.listen_for_public_responses,
            args=(5000, 25)
        )

        print("⏰ 3 saniye sonra saldırı başlayacak...")
        time.sleep(3)

        burst_thread.start()
        listen_thread.start()

        burst_thread.join()
        responses = listen_thread.join()

        # 6. Sonuçları analiz et
        if responses:
            successful_ports = set()
            for response in responses:
                successful_ports.add(response['source'][1])

            print(f"🎉 BAŞARILI! Çalışan portlar: {sorted(successful_ports)}")
            return sorted(successful_ports)
        else:
            print("❌ Hiç yanıt alınamadı")
            return None


# OTOMATİK PUBLIC RESPONDER
class PublicResponder:
    def __init__(self, respond_port=5000):
        self.respond_port = respond_port
        self.running = True

    def start_public_responder(self):
        """Gelen public burst'lara yanıt ver"""
        print(f"🌍 Public Responder: port {self.respond_port}")

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', self.respond_port))
        sock.settimeout(1)

        while self.running:
            try:
                data, addr = sock.recvfrom(1024)

                if b"PUBLIC_BURST" in data:
                    # Hemen yanıt gönder
                    response_msg = f"PUBLIC_RESPONSE_{time.time()}".encode()
                    sock.sendto(response_msg, addr)
                    print(f"⚡ Yanıt gönderildi: {addr}")

            except socket.timeout:
                continue
            except KeyboardInterrupt:
                break

        sock.close()


# KULLANIM
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "responder":
        # Public Responder modu
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
        responder = PublicResponder(port)
        try:
            responder.start_public_responder()
        except KeyboardInterrupt:
            responder.running = False
            print("🛑 Responder durduruldu")

    else:
        # Tam otomatik public saldırı
        target_input = input("Hedef IP/Domain: ").strip()

        puncher = PublicIPNATPuncher()
        result = puncher.automated_public_punch(target_input)

        if result:
            print(f"\n🎯 PUBLIC NAT DELİNDİ! Portlar: {result}")
        else:
            print("\n💥 Public NAT delme başarısız")