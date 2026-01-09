## Oracle Cloud Always Free Tier (2025)

Based on official Oracle documentation , here’s what you get permanently free:

**Compute Resources:**
- 4 OCPUs and 24 GB RAM for ARM-based Ampere A1 instances (can be split into up to 4 smaller VMs) 
- OR 2 AMD-based VMs with 1/8 OCPU and 1 GB RAM each
- 200 GB total Block Volume storage 

**Other Always Free Resources:**
- 2 Oracle Autonomous Databases
- 20 GB Object Storage (Standard, Infrequent Access, and Archive combined) 
- 10 TB monthly outbound data transfer 
- 1 Flexible Load Balancer (10 Mbps)
- 2 Virtual Cloud Networks (VCNs) 

**Plus $300 free trial credits for 30 days** to test paid services.

-----

## Complete n8n Setup Guide on Oracle Cloud

### Part 1: Create Oracle Cloud Account
1. Go to [Oracle Cloud](https://www.oracle.com/cloud/free/)
1. Sign up (requires credit card for verification, but won’t be charged)
1. **Important:** Choose your Home Region carefully during signup - Always Free services only run in your home region and this cannot be changed later 

### Part 2: Create ARM Compute Instance
1. **Navigate to Instances:**

   - Log into Oracle Cloud Console
   - Go to **Compute → Instances**
   - Click **Create Instance**

1. **Configure Instance:**

   - **Name:** `n8n-server` (or your choice)
   - **Image:** Ubuntu 22.04 or 24.04 (Minimal or Standard)
   - **Shape:** Click “Change Shape”
   - Select **VM.Standard.A1.Flex** (ARM-based)
   - Set **OCPUs:** 2-4 (recommend starting with 2)
   - Set **Memory:** 12-24 GB (recommend 12 GB)
   - Verify “Always Free-eligible” label appears

1. **Networking:**
   - Use default VCN or create new one
   - **Assign public IP:** Yes

1. **SSH Keys:**
   - Upload your public SSH key (generate with `ssh-keygen` if needed)
   - Save the private key securely

1. Click **Create** and wait for instance to provision
1. **Copy the Public IP** from the instance details page

### Part 3: Configure Oracle Cloud Network Security
1. **Go to your instance page** → Click on VCN name
1. Navigate to **Security Lists** → Click on your default security list
1. **Add Ingress Rules:**
   
   **Rule 1 - SSH:**
   - Source CIDR: `0.0.0.0/0` (or your IP for security)
   - IP Protocol: TCP
   - Destination Port: 22

   **Rule 2 - HTTP:**
   - Source CIDR: `0.0.0.0/0`
   - IP Protocol: TCP
   - Destination Port: 80  

   **Rule 3 - HTTPS:**
   - Source CIDR: `0.0.0.0/0`
   - IP Protocol: TCP
   - Destination Port: 443

   **Rule 4 - n8n (temporary for setup):**
   - Source CIDR: `0.0.0.0/0`
   - IP Protocol: TCP
   - Destination Port: 5678

### Part 4: Connect and Configure Server
1. **SSH into your instance:**
   ```bash
   ssh ubuntu@YOUR_PUBLIC_IP
   ```

1. **Update system:**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

1. **Critical: Fix Oracle Cloud firewall issues** (this solves common connectivity problems):
   ```bash
   sudo iptables -P INPUT ACCEPT
   sudo iptables -P OUTPUT ACCEPT
   sudo iptables -P FORWARD ACCEPT
   sudo iptables -F
   sudo apt install iptables-persistent -y
   
   # Confirm saving rules when prompted
   sudo netfilter-persistent save
   ```

1. **Configure UFW (software firewall):**
   ```bash
   #Install  Uncomplicated Firewall (ufw) command-line utility
   sudo apt install ufw
   
   sudo ufw allow 22/tcp    # SSH
   sudo ufw allow 80/tcp    # HTTP
   sudo ufw allow 443/tcp   # HTTPS
   sudo ufw allow 5678/tcp  # n8n (temporary)
   sudo ufw enable
   sudo ufw status verbose
   ```

1. **Reboot to apply all changes:**
   ```bash
   sudo reboot
   ```
   Wait 2-3 minutes, then SSH back in.

### Part 5: Install Docker
```bash
# Install Docker
sudo apt install -y docker.io docker-compose

# Add your user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Verify installation
docker --version
docker-compose --version
```

### Part 6: Deploy n8n with Docker
1. **Create n8n directory:**
   ```bash
   mkdir ~/n8n && cd ~/n8n
   ```

1. **Create docker-compose.yml:**
   ```bash
   nano docker-compose.yml
   ```

1. **Paste this configuration:**
   ```yaml
   version: '3'

   services:
     n8n:
       image: n8nio/n8n:latest
       container_name: n8n
       restart: unless-stopped

       ports:
         - "5678:5678"

       environment:
         - N8N_HOST=0.0.0.0
         - N8N_PORT=5678
         - N8N_PROTOCOL=http
         - GENERIC_TIMEZONE=America/New_York  # Change to your timezone
         - TZ=America/New_York

         # Basic auth (change these!)
         - N8N_BASIC_AUTH_ACTIVE=true
         - N8N_BASIC_AUTH_USER=admin
         - N8N_BASIC_AUTH_PASSWORD=ChangeThisPassword123!

       volumes:
         - ./n8n_data:/home/node/.n8n
   ```

1. **Set proper permissions:**
   ```bash
   mkdir n8n_data
   sudo chown -R 1000:1000 ./n8n_data
   ```

1. **Start n8n:**
   ```bash
   docker-compose up -d
   ```

1. **Check if running:**
   ```bash
   docker-compose ps
   docker-compose logs -f
   ```

1. **Test access:**
- Open browser to `http://YOUR_PUBLIC_IP:5678`
- You should see n8n login page
- Use the credentials from docker-compose.yml

### Part 7: (Optional) Add Domain & HTTPS

If you have a domain, you can add proper HTTPS:

1. **Point your domain to the server:**
   - Create an A record: `n8n.yourdomain.com` → `YOUR_PUBLIC_IP`

1. **Install Nginx:**
   ```bash
   sudo apt install -y nginx certbot python3-certbot-nginx
   ```

1. **Create Nginx config:**
   ```bash
   sudo nano /etc/nginx/sites-available/n8n
   ```

   ```nginx
   server {
       listen 80;
       server_name n8n.yourdomain.com;

       location / {
           proxy_pass http://localhost:5678;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;

           # WebSocket support
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
       }
   }
   ```

1. **Enable site and get SSL:**
   ```bash
   sudo ln -s /etc/nginx/sites-available/n8n /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl restart nginx
   sudo certbot --nginx -d n8n.yourdomain.com
   ```

1. **Update docker-compose.yml:**
   ```yaml
   environment:
     - N8N_PROTOCOL=https
     - WEBHOOK_URL=https://n8n.yourdomain.com
   ```

1. **Restart n8n:**
   ```bash
   docker-compose down && docker-compose up -d
   ```

1. **Remove port 5678 from UFW (now using Nginx):**
   ```bash
   sudo ufw delete allow 5678/tcp
   ```

### Maintenance Commands
```bash
# View logs
docker-compose logs -f

# Restart n8n
docker-compose restart

# Stop n8n
docker-compose down

# Update n8n
docker-compose pull
docker-compose up -d

# Backup data
tar -czf n8n_backup_$(date +%Y%m%d).tar.gz ~/n8n/n8n_data
```

### Common Issues & Solutions
**Can’t connect to n8n:**
- Verify OCI Security List rules are added
- Check UFW: `sudo ufw status`
- Verify container is running: `docker-compose ps`
- Check logs: `docker-compose logs`

**Permission errors:**
```bash
sudo chown -R 1000:1000 ~/n8n/n8n_data
```

**ARM compatibility issues:**
- n8n works great on ARM
- Docker images are multi-arch compatible

This setup gives you a production-ready n8n instance on Oracle Cloud’s free tier! The ARM instance is more than powerful enough for most automation workflows.