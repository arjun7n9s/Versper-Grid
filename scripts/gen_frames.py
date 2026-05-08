#!/usr/bin/env python3
"""Continuously generates animated synthetic Gazebo frames and posts them
to the ingest API. Simulates:
  - CCTV South: plume origin fixed, gas cloud drifts NE with wind, grows over time
  - Drone D-1:  orbits slowly around tank farm at constant altitude
  - CCTV Gate:  smoke column drifts across horizon, slight camera shake

Run: /opt/vespergrid-venv/bin/python3 /opt/vespergrid/scripts/gen_frames.py
"""
import httpx, io, math, time, random, sys

from PIL import Image, ImageDraw, ImageFilter

API = 'http://localhost:8742'
INTERVAL = 8   # seconds between frame bundles

def draw_scanlines(d, w, h, step=4):
    for y in range(0, h, step):
        d.line([(0,y),(w,y)], fill=(0,0,0), width=1)

def make_cctv_south(t: float) -> bytes:
    """Fixed camera, plume drifts NE, grows with time."""
    W, H = 640, 360
    img = Image.new('RGB', (W, H), (12, 18, 13))
    d   = ImageDraw.Draw(img)

    # ground
    d.rectangle([0, 260, W, H], fill=(14, 20, 14))
    # pipe rack left
    d.rectangle([30, 140, 70, 265], fill=(35, 60, 38))
    d.rectangle([30, 155, 160, 168], fill=(40, 65, 42))
    d.rectangle([30, 195, 160, 205], fill=(38, 62, 40))

    # tank body (cylindrical)
    d.rectangle([200, 80, 440, 260], fill=(28, 56, 32))
    d.ellipse(  [200, 65, 440, 108], fill=(33, 66, 37))
    d.ellipse(  [200, 248, 440, 288], fill=(23, 50, 27))
    # B-4 label
    d.text((295, 165), 'B-4', fill=(180, 220, 180))
    # flange breach point — fixed at tank shoulder
    bx, by = 310, 92

    # wind drift: plume origin fixed, tip drifts NE over time
    wind_x = 1.4   # pixels/sec eastward
    wind_y = -0.6  # pixels/sec upward
    age    = (t % 60)  # reset every 60s for demo loop
    growth = min(age * 1.8, 80)

    for i in range(12):
        frac   = i / 12.0
        cx     = int(bx + wind_x * age * frac + random.gauss(0, 2))
        cy     = int(by + wind_y * age * frac + random.gauss(0, 1.5))
        radius = int(8 + growth * frac + random.gauss(0, 1))
        alpha  = max(20, 200 - int(160 * frac))
        grey   = min(255, 160 + int(60 * frac))
        d.ellipse([cx-radius, cy-radius, cx+radius, cy+radius],
                  fill=(grey, grey, grey-20))

    # slight glow at breach point
    d.ellipse([bx-10, by-10, bx+10, by+10], fill=(230, 160, 30))

    draw_scanlines(d, W, H)
    d.rectangle([0, 325, W, H], fill=(0, 0, 0))
    d.text((10, 8),   'VesperGrid · Gazebo Sim', fill=(134, 215, 255))
    d.text((10, 328), 'CCTV SOUTH — TANK B-4 FLANGE', fill=(255, 200, 60))
    d.text((10, 344), f'Wind NE {wind_x:.1f} m/s · Plume age {age:.0f}s', fill=(160, 160, 160))
    d.text((465, 344), time.strftime('%H:%M:%S'), fill=(80, 80, 80))

    img = img.filter(ImageFilter.GaussianBlur(radius=0.4))
    buf = io.BytesIO(); img.save(buf, 'JPEG', quality=85); return buf.getvalue()


def make_drone_d1(t: float) -> bytes:
    """Drone orbits tank farm. Camera rotates with drone heading."""
    W, H = 640, 360
    img = Image.new('RGB', (W, H), (8, 12, 20))
    d   = ImageDraw.Draw(img)

    # orbit params — slow circle around centre of tank farm
    orbit_speed = 0.018   # rad/sec
    angle       = t * orbit_speed
    orbit_r     = 90      # pixel radius of orbit in image space

    # tank farm centre in image
    cx, cy = 320, 180
    # camera shift as drone orbits (parallax)
    shift_x = int(orbit_r * math.sin(angle) * 0.35)
    shift_y = int(orbit_r * math.cos(angle) * 0.12)

    # grid of tanks
    for col, row in [(0,0),(1,0),(2,0),(3,0),(0,1),(1,1),(2,1),(3,1)]:
        tx = cx - 140 + col*90 + shift_x
        ty = cy - 60  + row*85 + shift_y
        clr = (220, 140, 20) if (col==1 and row==1) else (22, 50, 28)
        out = (220, 140, 20) if (col==1 and row==1) else (42, 90, 48)
        d.ellipse([tx-30, ty-18, tx+30, ty+18], fill=clr, outline=out, width=2)

    # pipe racks
    for px in range(cx-155+shift_x, cx+170+shift_x, 45):
        d.line([(px, cy-85+shift_y),(px, cy+110+shift_y)], fill=(35, 65, 40), width=2)

    # plume from B-4 drifting NE — visible from above
    plume_age = t % 60
    bx = cx - 140 + 1*90 + shift_x
    by = cy - 60  + 1*85 + shift_y
    for i in range(8):
        frac = i/8.0
        px2  = int(bx + 22*frac + random.gauss(0,1))
        py2  = int(by - 14*frac + random.gauss(0,1))
        r2   = int(6 + min(plume_age,40)*frac*0.5)
        grey = min(255, 140+int(80*frac))
        d.ellipse([px2-r2,py2-r2,px2+r2,py2+r2], fill=(grey,grey,grey-15))

    # drone shadow indicator (centre crosshair)
    dx = cx + int(orbit_r * math.sin(angle+math.pi)) + shift_x//2
    dy = cy + int(orbit_r * math.cos(angle+math.pi) * 0.3) + shift_y//2
    d.line([(dx-12,dy),(dx+12,dy)], fill=(255,255,200,120), width=1)
    d.line([(dx,dy-8),(dx,dy+8)],   fill=(255,255,200,120), width=1)
    d.ellipse([dx-3,dy-3,dx+3,dy+3], fill=(255,200,100))

    draw_scanlines(d, W, H, step=5)
    d.rectangle([0, 325, W, H], fill=(0, 0, 0))
    d.text((10, 8),   'VesperGrid · Gazebo Sim', fill=(134, 215, 255))
    heading = math.degrees(angle) % 360
    d.text((10, 328), f'DRONE D-1 — HEADING {heading:.0f}° · ALT 30m', fill=(120, 190, 255))
    d.text((10, 344), f'Orbit angle {math.degrees(angle)%360:.1f}°  B-4 plume visible', fill=(160,160,160))
    d.text((465, 344), time.strftime('%H:%M:%S'), fill=(80, 80, 80))

    img = img.filter(ImageFilter.GaussianBlur(radius=0.3))
    buf = io.BytesIO(); img.save(buf,'JPEG',quality=85); return buf.getvalue()


def make_cctv_gate(t: float) -> bytes:
    """Wide-angle gate view. Smoke column drifts across horizon. Slight shake."""
    W, H = 640, 360
    # tiny random camera shake
    shake_x = int(random.gauss(0, 1.2))
    shake_y = int(random.gauss(0, 0.8))
    img = Image.new('RGB', (W, H), (14, 14, 12))
    d   = ImageDraw.Draw(img)

    # sky gradient (very dark)
    for y in range(180):
        v = int(12 + y*0.06)
        d.line([(0,y+shake_y),(W,y+shake_y)], fill=(v,v+1,v-1))

    # ground
    d.rectangle([0+shake_x, 200+shake_y, W+shake_x, H], fill=(16, 20, 15))
    d.rectangle([0+shake_x, 196+shake_y, W+shake_x, 204+shake_y], fill=(30,30,28))

    # fence
    for x in range(20+shake_x, 620+shake_x, 55):
        d.rectangle([x,   95+shake_y, x+7,  200+shake_y], fill=(46,66,46))
        d.line([(x,115+shake_y),(x+48,115+shake_y)], fill=(56,76,56))
        d.line([(x,145+shake_y),(x+48,145+shake_y)], fill=(56,76,56))
        d.line([(x,175+shake_y),(x+48,175+shake_y)], fill=(56,76,56))

    # guardhouse
    d.rectangle([255+shake_x,108+shake_y,385+shake_x,200+shake_y], fill=(18,42,22))
    d.rectangle([288+shake_x,152+shake_y,352+shake_x,200+shake_y], fill=(14,33,18))

    # smoke column drifts east over time
    drift = (t * 1.8) % W
    smoke_base_x = int(80 + drift)
    plume_age = t % 60
    for i in range(10):
        frac  = i / 10.0
        sx    = int(smoke_base_x + i*4 + random.gauss(0,2))
        sy    = int(160 - i*14 + shake_y)
        sr    = int(10 + plume_age*0.6*frac + random.gauss(0,1.5))
        grey  = min(255, 110+int(90*frac))
        if 0 < sx < W and 0 < sy < H:
            d.ellipse([sx-sr,sy-sr,sx+sr,sy+sr], fill=(grey,grey,grey-12))

    draw_scanlines(d, W, H)
    d.rectangle([0, 325, W, H], fill=(0, 0, 0))
    d.text((10+shake_x, 8+shake_y),   'VesperGrid · Gazebo Sim', fill=(134,215,255))
    d.text((10, 328), 'CCTV GATE — NORTH PERIMETER', fill=(200,200,100))
    d.text((10, 344), f'Smoke drift E · Column at x={smoke_base_x}px', fill=(160,160,160))
    d.text((465, 344), time.strftime('%H:%M:%S'), fill=(80,80,80))

    img = img.filter(ImageFilter.GaussianBlur(radius=0.5))
    buf = io.BytesIO(); img.save(buf,'JPEG',quality=85); return buf.getvalue()


def run():
    print('VesperGrid frame generator — posting every', INTERVAL, 'seconds')
    print('Ctrl+C to stop')
    t0 = time.time()
    i  = 0
    while True:
        t = time.time() - t0
        frames = [
            ('cctv_south_frame.jpg', make_cctv_south(t)),
            ('drone_d1_frame.jpg',   make_drone_d1(t)),
            ('cctv_gate_frame.jpg',  make_cctv_gate(t)),
        ]
        files = [('images',(n,d,'image/jpeg')) for n,d in frames]
        try:
            r = httpx.post(
                f'{API}/api/ingest/upload',
                files=files,
                data={
                    'location':    'Tank B-4 Flange · Northgate LNG Terminal',
                    'field_notes': f'Frame bundle #{i} — t={t:.0f}s. Gas plume drifting NE. Drone D-1 orbit. Gate CCTV nominal.',
                    'sensor_count':'3',
                },
                timeout=30,
            )
            j = r.json()
            print(f'[{time.strftime("%H:%M:%S")}] bundle #{i}  job={j["job_id"]}  backend={j["backend"]}')
        except Exception as e:
            print(f'[{time.strftime("%H:%M:%S")}] ERROR: {e}')
        i += 1
        time.sleep(INTERVAL)

if __name__ == '__main__':
    run()
