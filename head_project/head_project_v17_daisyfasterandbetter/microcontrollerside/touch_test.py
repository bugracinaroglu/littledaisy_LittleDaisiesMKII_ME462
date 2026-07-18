from time import sleep_ms
import rp2350_touch_lcd_128 as board


# LCD başlat
LCD = board.LCD_1inch28()
LCD.set_bl_pwm(65535)

# Touch başlat
# Önce orijinal demo ile aynı default pinleri deniyoruz.
Touch = board.Touch_CST816T(mode=1, LCD=LCD)

# Touch point mode
Touch.Mode = 1
Touch.Set_Mode(1)
Touch.Flag = 0
Touch.X_point = 0
Touch.Y_point = 0

touch_count = 0

LCD.fill(LCD.black)
LCD.text("TOUCH TEST", 75, 30, LCD.white)
LCD.text("Touch screen", 65, 65, LCD.white)
LCD.text("Waiting...", 80, 105, LCD.green)
LCD.show()

while True:
    if Touch.Flag == 1:
        Touch.Flag = 0
        touch_count += 1

        x = Touch.X_point
        y = Touch.Y_point

        # ekran disina cikmasin
        if x < 0:
            x = 0
        if x > 239:
            x = 239
        if y < 0:
            y = 0
        if y > 239:
            y = 239

        LCD.fill(LCD.black)

        LCD.text("TOUCH OK", 85, 25, LCD.green)
        LCD.text("X: {}".format(x), 70, 70, LCD.white)
        LCD.text("Y: {}".format(y), 70, 95, LCD.white)
        LCD.text("Count: {}".format(touch_count), 70, 120, LCD.white)

        # Dokunulan noktaya arti isareti ciz
        LCD.line(x - 10, y, x + 10, y, LCD.red)
        LCD.line(x, y - 10, x, y + 10, LCD.red)
        LCD.fill_rect(x - 2, y - 2, 5, 5, LCD.blue)

        LCD.show()

        print("Touch:", x, y, "Count:", touch_count)

    sleep_ms(20)