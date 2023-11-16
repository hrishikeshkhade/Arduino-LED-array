#define CLK 13
#define DIN 11
#define CS  10
#define X_SEGMENTS   4
#define Y_SEGMENTS   4
#define NUM_SEGMENTS (X_SEGMENTS * Y_SEGMENTS)

// a framebuffer to hold the state of the entire matrix of LEDs
// laid out in raster order, with (0, 0) at the top-left
byte fb[8 * NUM_SEGMENTS];


void shiftAll(byte send_to_address, byte send_this_data)
{
  digitalWrite(CS, LOW);
  for (int i = 0; i < NUM_SEGMENTS; i++) {
    shiftOut(DIN, CLK, MSBFIRST, send_to_address);
    shiftOut(DIN, CLK, MSBFIRST, send_this_data);
  }
  digitalWrite(CS, HIGH);
}


void setup() {
  Serial.begin(115200);
  pinMode(CLK, OUTPUT);
  pinMode(DIN, OUTPUT);
  pinMode(CS, OUTPUT);

  // Setup each MAX7219
  shiftAll(0x0f, 0x00); //display test register - test mode off
  shiftAll(0x0b, 0x07); //scan limit register - display digits 0 thru 7
  shiftAll(0x0c, 0x01); //shutdown register - normal operation
  shiftAll(0x0a, 0x0f); //intensity register - max brightness
  shiftAll(0x09, 0x00); //decode mode register - No decode
}


void loop() {
  static int16_t sx1 = 15 << 8, sx2 = sx1, sy1, sy2;
  sx1 = sx1 - (sy1 >> 6);
  sy1 = sy1 + (sx1 >> 6);
  sx2 = sx2 - (sy2 >> 5);
  sy2 = sy2 + (sx2 >> 5);

  static byte travel = 0;
  travel--;
  byte *dst = fb;
  byte output = 0;
  int8_t x_offset = (sx1 >> 8) - X_SEGMENTS * 4;
  int8_t y_offset = (sx2 >> 8) - Y_SEGMENTS * 4;

  uint8_t  screenx, screeny, xroot, yroot;
  uint16_t xsumsquares, ysumsquares, xnextsquare, ynextsquare;
  int8_t   x, y;

  // offset the origin in screen space
  x = x_offset;
  y = y_offset;
  ysumsquares = x_offset * x_offset + y * y;
  yroot = int(sqrtf(ysumsquares));
  ynextsquare = yroot*yroot;

  // Quadrant II (top-left)
  screeny = Y_SEGMENTS * 8;
  while (y < 0 && screeny) {
    x = x_offset;
    screenx = X_SEGMENTS * 8;
    xsumsquares = ysumsquares;
    xroot = yroot;
    if (x < 0) {
      xnextsquare = xroot * xroot;
      while (x < 0 && screenx) {
        screenx--;
        output <<= 1;
        output |= ((xroot + travel) & 8) >> 3;
        if (!(screenx & 7))
          *dst++ = output;
        xsumsquares += 2 * x++ + 1;
        if (xsumsquares < xnextsquare)
          xnextsquare -= 2 * xroot-- - 1;
      }
    }
    // Quadrant I (top right)
    if (screenx) {
      xnextsquare = (xroot + 1) * (xroot + 1);
      while (screenx) {
        screenx--;
        output <<= 1;
        output |= ((xroot + travel) & 8) >> 3;
        if (!(screenx & 7))
          *dst++ = output;
        xsumsquares += 2 * x++ + 1;
        if (xsumsquares >= xnextsquare)
          xnextsquare += 2 * ++xroot + 1;
      }
    }
    ysumsquares += 2 * y++ + 1;
    if (ysumsquares < ynextsquare)
      ynextsquare -= 2 * yroot-- - 1;
    screeny--;
  }
  // Quadrant III (bottom left)
  ynextsquare = (yroot + 1) * (yroot + 1);
  while (screeny) {
    x = x_offset;
    screenx = X_SEGMENTS * 8;
    xsumsquares = ysumsquares;
    xroot = yroot;
    if (x < 0) {
      xnextsquare = xroot * xroot;
      while (x < 0 && screenx) {
        screenx--;
        output <<= 1;
        output |= ((xroot + travel) & 8) >> 3;
        if (!(screenx & 7))
          *dst++ = output;
        xsumsquares += 2 * x++ + 1;
        if (xsumsquares < xnextsquare)
          xnextsquare -= 2 * xroot-- - 1;
      }
    }
    // Quadrant IV (bottom right)
    if (screenx) {
      xnextsquare = (xroot + 1) * (xroot + 1);
      while (screenx--) {
        output <<= 1;
        output |= ((xroot + travel) & 8) >> 3;
        if (!(screenx & 7))
          *dst++ = output;
        xsumsquares += 2 * x++ + 1;
        if (xsumsquares >= xnextsquare)
          xnextsquare += 2 * ++xroot + 1;
      }
    }
    ysumsquares += 2 * y++ + 1;
    if (ysumsquares >= ynextsquare)
      ynextsquare += 2 * ++yroot + 1;
    screeny--;
  }

  show();
}


void set_pixel(uint8_t x, uint8_t y, uint8_t mode) {
  byte *addr = &fb[x / 8 + y * X_SEGMENTS];
  byte mask = 128 >> (x % 8);
  switch (mode) {
    case 0: // clear pixel
      *addr &= ~mask;
      break;
    case 1: // plot pixel
      *addr |= mask;
      break;
    case 2: // XOR pixel
      *addr ^= mask;
      break;
  }
}


void safe_pixel(uint8_t x, uint8_t y, uint8_t mode) {
  if ((x >= X_SEGMENTS * 8) || (y >= Y_SEGMENTS * 8))
    return;
  set_pixel(x, y, mode);
}


// turn off every LED in the framebuffer
void clear() {
  byte *addr = fb;
  for (byte i = 0; i < 8 * NUM_SEGMENTS; i++)
    *addr++ = 0;
}


// send the raster order framebuffer in the correct order
// for the boustrophedon layout of daisy-chained MAX7219s
void show() {
  for (byte row = 0; row < 8; row++) {
    digitalWrite(CS, LOW);
    byte segment = NUM_SEGMENTS;
    while (segment--) {
      byte x = segment % X_SEGMENTS;
      byte y = segment / X_SEGMENTS * 8;
      byte addr = (row + y) * X_SEGMENTS;

      if (segment & X_SEGMENTS) { // odd rows of segments
        shiftOut(DIN, CLK, MSBFIRST, 8 - row);
        shiftOut(DIN, CLK, LSBFIRST, fb[addr + x]);
      } else { // even rows of segments
        shiftOut(DIN, CLK, MSBFIRST, 1 + row);
        shiftOut(DIN, CLK, MSBFIRST, fb[addr - x + X_SEGMENTS - 1]);
      }
    }
    digitalWrite(CS, HIGH);
  }
}
