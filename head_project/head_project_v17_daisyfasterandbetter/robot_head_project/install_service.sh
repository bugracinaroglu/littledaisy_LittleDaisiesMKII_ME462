#!/bin/bash
echo "Installing Daisy Head Systemd Service..."
sudo cp daisy_head.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable daisy_head.service
sudo systemctl start daisy_head.service
echo "Service installed and started!"
echo "To check the logs, run: sudo journalctl -u daisy_head.service -f"
echo "To stop it, run: sudo systemctl stop daisy_head.service"
