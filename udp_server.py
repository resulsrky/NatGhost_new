# Dosya Adı: udp_server.py
# Amaç: İstemcinin genel IP ve port bilgisini geri yansıtan sunucu.

import socket

HOST = '0.0.0.0'  # Tüm ağ arayüzlerinden gelen bağlantıları kabul et
PORT = 12345      # İstemcinin bağlanacağı port

# AF_INET: IPv4, SOCK_DGRAM: UDP
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    # Sunucuyu belirtilen adrese ve porta bağla
    s.bind((HOST, PORT))
    print(f"UDP Sunucusu {HOST}:{PORT} adresinde dinlemede...")
    print("İstemcinin gördüğü genel IP ve Port bilgisini geri gönderecek.")

    # Sürekli olarak gelen paketleri dinle
    while True:
        # Bir paket gelene kadar bekle. data = mesaj, addr = (istemci_ip, istemci_port)
        data, addr = s.recvfrom(1024)

        # Gelen isteği terminale yazdır (kontrol için)
        # print(f"İstek geldi: {addr} | Veri: {data.decode('utf-8')}")

        # İstemciye kendi adres bilgisini ('IP:PORT' formatında) geri gönder
        response_message = f"{addr[0]}:{addr[1]}"
        s.sendto(response_message.encode('utf-8'), addr)