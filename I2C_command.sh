sudo i2cdetect -l
sleep 0.01  
sudo i2cdetect -r -y 9
sleep 0.01                    
sudo i2ctransfer -f -y 9 w2@0x6b 0x00 0x06 r1
sleep 0.01                     
sudo i2ctransfer -f -y 9 w2@0x6b 0x00 0x1a r1 
sleep 0.01                     
sudo i2ctransfer -f -y 9 w2@0x6b 0x00 0x0a r1
sleep 0.01                     
sudo i2ctransfer -f -y 9 w2@0x6b 0x00 0x0b r1
sleep 0.01                     
sudo i2ctransfer -f -y 9 w2@0x6b 0x00 0x0c r1
sleep 0.01                     
sudo i2ctransfer -f -y 9 w2@0x6b 0x01 0x08 r1
sleep 0.01                    
sudo i2ctransfer -f -y 9 w2@0x6b 0x01 0x1a r1
sleep 0.01                    
sudo i2ctransfer -f -y 9 w2@0x6b 0x01 0x2c r1
sleep 0.01                     
sudo i2ctransfer -f -y 9 w2@0x6b 0x01 0x3E r1
sleep 0.01                    
sudo i2ctransfer -f -y 9 w2@0x6b 0x01 0x50 r1
sleep 0.01                     
sudo i2ctransfer -f -y 9 w2@0x6b 0x01 0x68 r1
sleep 0.01                    
sudo i2ctransfer -f -y 9 w2@0x6b 0x01 0x7a r1
sleep 0.01                     
sudo i2ctransfer -f -y 9 w2@0x6b 0x01 0x8c r1
sleep 0.01                     
sudo i2ctransfer -f -y 9 w2@0x6b 0x08 0xD0 r1
sleep 0.01                   
sudo i2ctransfer -f -y 9 w2@0x6b 0x08 0xD0 r1
sleep 0.01                    
sudo i2ctransfer -f -y 9 w2@0x6b 0x08 0xD0 r1
sleep 0.01                    
sudo i2ctransfer -f -y 9 w2@0x6b 0x08 0xD0 r1
sleep 0.01                     
sudo i2ctransfer -f -y 9 w2@0x6b 0x08 0xD0 r1
sleep 0.01                    
sudo i2ctransfer -f -y 9 w2@0x6b 0x11 0xD0 r1
sleep 0.01       
sudo i2ctransfer -f -y 9 w2@0x6b 0x08 0xD1 r1
sleep 0.01                   
sudo i2ctransfer -f -y 9 w2@0x6b 0x08 0xD1 r1
sleep 0.01                    
sudo i2ctransfer -f -y 9 w2@0x6b 0x08 0xD1 r1
sleep 0.01                    
sudo i2ctransfer -f -y 9 w2@0x6b 0x08 0xD1 r1
sleep 0.01                     
sudo i2ctransfer -f -y 9 w2@0x6b 0x08 0xD1 r1
sleep 0.01                    
sudo i2ctransfer -f -y 9 w2@0x6b 0x11 0xD0 r1
sleep 0.01                   
sudo i2ctransfer -f -y 9 w2@0x6b 0x11 0xe1 r1
sleep 0.01                     
sudo i2ctransfer -f -y 9 w2@0x6b 0x11 0xe5 r1
sleep 0.01                     
sudo i2ctransfer -f -y 9 w2@0x6b 0x11 0xe9 r1
sleep 0.01                     
sudo i2ctransfer -f -y 9 w2@0x6b 0x04 0x38 r1
sleep 0.01                     
sudo i2ctransfer -f -y 9 w2@0x6b 0x00 0x35 r1
sleep 0.01                     
sudo i2ctransfer -f -y 9 w2@0x6b 0x00 0x36 r1
sleep 0.01                     
sudo i2ctransfer -f -y 9 w2@0x6b 0x00 0x37 r1
sleep 0.01                     
sudo i2ctransfer -f -y 9 w2@0x6b 0x00 0x38 r1
sleep 0.01

#0x44 represent the the I2C address of MAX9295/MAX96717/MAX96717F
#Modify the 0x44 to the actual address according to the port to which the camera is connected.
sudo i2ctransfer -f -y 9 w2@0x44 0x01 0x02 r1
sleep 0.01
sudo i2ctransfer -f -y 9 w2@0x44 0x01 0x0a r1
sleep 0.01
sudo i2ctransfer -f -y 9 w2@0x44 0x01 0x12 r1
sleep 0.01
sudo i2ctransfer -f -y 9 w2@0x44 0x01 0x1a r1
sleep 0.01
sudo i2ctransfer -f -y 9 w2@0x44 0x05 0x5d r1
sleep 0.01
sudo i2ctransfer -f -y 9 w2@0x44 0x05 0x5e r1
sleep 0.01
sudo i2ctransfer -f -y 9 w2@0x44 0x05 0x5f r1
sleep 0.01
sudo i2ctransfer -f -y 9 w2@0x44 0x05 0x60 r1
sleep 0.01