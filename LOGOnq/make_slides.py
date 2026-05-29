from PIL import Image, ImageDraw, ImageFont
import os

W, H = 1080, 1080
BG = (13, 17, 23)
ACCENT = (56, 189, 248)
ACCENT2 = (139, 92, 246)
GREEN = (34, 197, 94)
RED = (239, 68, 68)
ORANGE = (249, 115, 22)
WHITE = (255, 255, 255)
GRAY = (156, 163, 175)
DARK_CARD = (30, 41, 59)
GOLD = (234, 179, 8)

def get_font(size, bold=False):
    if bold:
        paths = ['C:/Windows/Fonts/arialbd.ttf', 'C:/Windows/Fonts/segoebd.ttf']
    else:
        paths = ['C:/Windows/Fonts/arial.ttf', 'C:/Windows/Fonts/segoeui.ttf']
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def text_width(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]

def center_x(draw, text, font, y, fill):
    w = text_width(draw, text, font)
    x = (W - w) // 2
    draw.text((x, y), text, font=font, fill=fill)
    return x, w

# ============================================================
# Slide 1: Cover
# ============================================================
img = Image.new('RGB', (W, H), BG)
draw = ImageDraw.Draw(img)

f_huge = get_font(72, True)
f_title = get_font(42, True)
f_sub = get_font(26, False)
f_body = get_font(22, False)
f_small = get_font(18, False)
f_big = get_font(52, True)
f_label = get_font(16, True)
f_med = get_font(28, False)

# Gradient background
for i in range(H):
    r = int(13 + (i/H) * 20)
    g = int(17 + (i/H) * 15)
    b = int(23 + (i/H) * 40)
    draw.line([(0, i), (W, i)], fill=(r, g, b))

cx, cy = W//2, 280
draw.ellipse([cx-100, cy-100, cx+100, cy+100], outline=ACCENT, width=4)
draw.text((cx-45, cy-35), 'NQ', font=get_font(60, True), fill=ACCENT)

center_x(draw, 'NeuralQuant', f_huge, 420, WHITE)
center_x(draw, 'AI-Powered Stock Analysis', f_sub, 510, GRAY)
center_x(draw, 'Multi-Agent AI  |  6-Factor Scoring  |  US + India', f_small, 580, GRAY)

features = ['PARA-DEBATE', 'Ask AI', 'Screener', 'Backtest']
tag_w, tag_h = 180, 60
pad = 20
total_w = len(features) * tag_w + (len(features) - 1) * pad
fx = (W - total_w) // 2
for label in features:
    draw.rounded_rectangle([fx, 680, fx+tag_w, 680+tag_h], radius=10, fill=DARK_CARD)
    lw = text_width(draw, label, f_small)
    draw.text((fx + (tag_w - lw)//2, 700), label, font=f_small, fill=WHITE)
    fx += tag_w + pad

center_x(draw, 'Free during development', f_body, 820, GREEN)
center_x(draw, 'neuralquant.co', f_label, H-60, ACCENT)

img.save('LOGOnq/slide_01.png', quality=95)
print('Slide 1 done')

# ============================================================
# Slide 2: PARA-DEBATE Overview
# ============================================================
img = Image.new('RGB', (W, H), BG)
draw = ImageDraw.Draw(img)

draw.rectangle([0, 0, W, 90], fill=(23, 32, 48))
draw.text((40, 22), '02', font=f_big, fill=ACCENT)
draw.text((130, 30), 'PARA-DEBATE ENGINE', font=f_title, fill=WHITE)
draw.text((130, 68), '5 specialist agents debate every stock', font=f_small, fill=GRAY)

agents = [
    ('FUNDAMENTAL', 'Value, Quality, Growth', ACCENT),
    ('TECHNICAL', 'Momentum, Trend, Levels', ACCENT2),
    ('SENTIMENT', 'News, Social, Analysts', GREEN),
    ('MACRO', 'Rates, FX, Commodities', ORANGE),
    ('HEAD ANALYST', 'Synthesizes + Verdict', WHITE),
]

y = 120
for i, (name, desc, color) in enumerate(agents):
    card_y = y + i * 110
    draw.rounded_rectangle([60, card_y, 1020, card_y+90], radius=12, fill=DARK_CARD)
    draw.text((80, card_y+10), name, font=get_font(24, True), fill=color)
    draw.text((80, card_y+45), desc, font=f_small, fill=GRAY)
    # connector line
    if i < len(agents) - 1:
        draw.line([(540, card_y+90), (540, card_y+110)], fill=ACCENT, width=2)
        draw.polygon([(530, card_y+110), (540, card_y+120), (550, card_y+110)], fill=ACCENT)

y2 = y + len(agents) * 110 + 20
draw.rounded_rectangle([60, y2, 1020, y2+70], radius=12, fill=(20, 40, 60))
draw.text((80, y2+10), 'ADVERSARIAL AGENT', font=get_font(24, True), fill=RED)
draw.text((80, y2+40), 'Mandatory contrarian - forces every bull thesis to survive worst-case scrutiny', font=f_small, fill=GRAY)

draw.text((60, H-60), 'NeuralQuant', font=f_label, fill=ACCENT)
draw.text((960, H-60), '2/8', font=f_small, fill=GRAY)
img.save('LOGOnq/slide_02.png', quality=95)
print('Slide 2 done')

# ============================================================
# Slide 3: Stock Score (FIXED - no overlap)
# ============================================================
img = Image.new('RGB', (W, H), BG)
draw = ImageDraw.Draw(img)

draw.rectangle([0, 0, W, 90], fill=(23, 32, 48))
draw.text((40, 22), '03', font=f_big, fill=ACCENT)
draw.text((130, 30), 'STOCK SCORE', font=f_title, fill=WHITE)
draw.text((130, 68), 'AAPL — Apple Inc.  |  5-Factor Quant Engine', font=f_small, fill=GRAY)

# Score card - tightened height so it doesn't run into TOP DRIVERS
y_card = 110
card_h = 360  # was effectively larger before
draw.rounded_rectangle([60, y_card, 1020, y_card+card_h], radius=16, fill=DARK_CARD)

# Big score
draw.text((100, y_card+20), '6', font=get_font(96, True), fill=ACCENT2)
draw.text((210, y_card+35), '/10', font=f_sub, fill=GRAY)
draw.text((100, y_card+110), 'Risk-On Regime', font=get_font(24, True), fill=GREEN)
draw.text((100, y_card+145), 'Composite: 0.552  |  Confidence: Low', font=f_small, fill=GRAY)

# Factor bars inside card - moved up to fit
factors = [
    ('Low Volatility', 100, GREEN),
    ('Low Short Interest', 100, GREEN),
    ('Value (P/E + P/B)', 45, ORANGE),
    ('Insider Cluster', 50, ORANGE),
    ('12-1 Momentum', 30, RED),
    ('Quality Composite', 20, RED),
]
bar_y_start = y_card + 185
bar_w = 500
for i, (label, pct, color) in enumerate(factors):
    by = bar_y_start + i * 28
    draw.text((100, by), label, font=f_small, fill=GRAY)
    draw.rounded_rectangle([340, by, 340+bar_w, by+18], radius=5, fill=(30, 40, 55))
    fw = int(bar_w * pct / 100)
    draw.rounded_rectangle([340, by, 340+fw, by+18], radius=5, fill=color)

# TOP DRIVERS - placed well below card with clear gap
y_drivers = y_card + card_h + 30
draw.text((60, y_drivers), 'TOP DRIVERS', font=f_label, fill=WHITE)

drivers = [
    ('+1.0', 'Low Volatility', '100%', GREEN),
    ('+1.0', 'Low Short Interest', '100%', GREEN),
    ('-0.6', 'Quality Composite', '20%', RED),
    ('-0.4', '12-1 Momentum', '30%', RED),
    ('-0.1', 'Value (P/E + P/B)', '45%', ORANGE),
]
for i, (score, name, pct, color) in enumerate(drivers):
    row_y = y_drivers + 30 + i * 42
    draw.rounded_rectangle([60, row_y, 140, row_y+32], radius=8, outline=color, width=2)
    draw.text((72, row_y+6), score, font=f_small, fill=color)
    draw.text((155, row_y+6), name, font=f_small, fill=WHITE)
    draw.text((900, row_y+6), pct, font=f_small, fill=color)

# HOW IT WORKS at bottom
y_how = H - 100
draw.text((60, y_how), 'HOW IT WORKS', font=f_label, fill=WHITE)
draw.text((60, y_how+22), 'Each stock scored 1-10 on 5 quant factors, percentile-ranked vs 500+ peers.', font=f_small, fill=GRAY)

draw.text((60, H-40), 'NeuralQuant', font=f_label, fill=ACCENT)
draw.text((960, H-40), '3/8', font=f_small, fill=GRAY)
img.save('LOGOnq/slide_03.png', quality=95)
print('Slide 3 done')

# ============================================================
# Slide 4: Adversarial Agent (FIXED - card tall enough)
# ============================================================
img = Image.new('RGB', (W, H), BG)
draw = ImageDraw.Draw(img)

draw.rectangle([0, 0, W, 90], fill=(23, 32, 48))
draw.text((40, 22), '04', font=f_big, fill=ACCENT)
draw.text((130, 30), 'THE ADVERSARIAL AGENT', font=f_title, fill=WHITE)
draw.text((130, 68), 'Mandated bear - stops groupthink dead', font=f_small, fill=GRAY)

# Red info box
draw.rounded_rectangle([60, 120, 1020, 280], radius=16, fill=(50, 15, 15))
draw.rounded_rectangle([60, 120, 1020, 280], radius=16, outline=RED, width=2)
draw.text((100, 145), 'ADVERSARIAL AGENT', font=f_title, fill=RED)
draw.text((100, 200), 'Mandatory contrarian role - always argues the BEAR case', font=f_body, fill=(220, 180, 180))
draw.text((100, 235), 'Forces every bull thesis to survive worst-case scrutiny', font=f_body, fill=(220, 180, 180))

y = 320
draw.rounded_rectangle([60, y, 500, y+80], radius=12, fill=DARK_CARD)
draw.text((80, y+10), '5 Specialist Agents', font=f_body, fill=WHITE)
draw.text((80, y+40), 'Bull + Bear arguments', font=f_small, fill=GRAY)

draw.line([510, y+40, 540, y+40], fill=ACCENT, width=3)
draw.polygon([(540, y+30), (560, y+40), (540, y+50)], fill=ACCENT)

draw.rounded_rectangle([560, y, 1020, y+80], radius=12, fill=(50, 15, 15))
draw.text((580, y+10), 'ADVERSARIAL', font=f_body, fill=RED)
draw.text((580, y+40), 'Challenges consensus', font=f_small, fill=(220, 180, 180))

y2 = y + 100
draw.line([540, y+80, 540, y2], fill=ACCENT, width=3)
draw.polygon([(530, y2), (540, y2+20), (550, y2)], fill=ACCENT)

# FIXED: increased card height from 180 to 240 so bars fit inside
y3 = y2 + 30
card_h = 240  # was 180
draw.rounded_rectangle([60, y3, 1020, y3+card_h], radius=16, fill=DARK_CARD)
draw.text((100, y3+15), 'VERDICT CLAMPING', font=f_title, fill=GOLD)
draw.text((100, y3+60), 'Head Analyst verdict clamped +/-2 tiers from consensus.', font=f_body, fill=WHITE)
draw.text((100, y3+90), 'If 5 agents say BUY (8/10), Adversarial can push to 6/10 max.', font=f_small, fill=GRAY)
draw.text((100, y3+115), 'Prevents extreme optimism even with strong consensus.', font=f_small, fill=GRAY)

# Bars moved up slightly to fit inside the taller card
y4 = y3 + 160
draw.text((100, y4), 'Consensus 8/10', font=f_small, fill=GREEN)
draw.rounded_rectangle([300, y4-2, 600, y4+22], radius=6, fill=(30, 60, 30))
draw.rounded_rectangle([300, y4-2, 480, y4+22], radius=6, fill=GREEN)
draw.text((620, y4), 'BUY', font=f_label, fill=GREEN)

y5 = y4 + 40
draw.text((100, y5), 'Clamped   6/10', font=f_small, fill=ORANGE)
draw.rounded_rectangle([300, y5-2, 600, y5+22], radius=6, fill=(60, 40, 10))
draw.rounded_rectangle([300, y5-2, 420, y5+22], radius=6, fill=ORANGE)
draw.text((620, y5), 'HOLD+', font=f_label, fill=ORANGE)

draw.text((60, H-60), 'NeuralQuant', font=f_label, fill=ACCENT)
draw.text((960, H-60), '4/8', font=f_small, fill=GRAY)
img.save('LOGOnq/slide_04.png', quality=95)
print('Slide 4 done')

# ============================================================
# Slide 5: Ask AI
# ============================================================
img = Image.new('RGB', (W, H), BG)
draw = ImageDraw.Draw(img)

draw.rectangle([0, 0, W, 90], fill=(23, 32, 48))
draw.text((40, 22), '05', font=f_big, fill=ACCENT)
draw.text((130, 30), 'ASK AI - NATURAL LANGUAGE', font=f_title, fill=WHITE)
draw.text((130, 68), 'Query any stock in plain English', font=f_small, fill=GRAY)

y = 120
draw.rounded_rectangle([60, y, 1020, y+130], radius=16, fill=DARK_CARD)
draw.text((100, y+15), 'User Query', font=f_body, fill=ACCENT)
draw.text((100, y+50), '"Is Apple a good buy right now given', font=f_body, fill=WHITE)
draw.text((100, y+78), 'the recent AI announcements?"', font=f_body, fill=WHITE)

y2 = y + 160
draw.rounded_rectangle([60, y2, 1020, y2+400], radius=16, fill=(20, 30, 45))
draw.text((100, y2+15), 'NeuralQuant AI Response', font=f_body, fill=GREEN)
draw.line([(100, y2+50), (980, y2+50)], fill=(40, 55, 75), width=1)

lines = [
    ('AAPL Score: 6/10 (HOLD+)', WHITE),
    ('', WHITE),
    ('Momentum is the strongest driver (+30%), fueled by', GRAY),
    ('the Vision Pro launch and Services revenue growth.', GRAY),
    ('', WHITE),
    ('However, valuation remains stretched (P/E 31.2x vs', GRAY),
    ('sector 24.1x), and the ADVERSARIAL agent flags', GRAY),
    ('iPhone revenue decline risk in China markets.', GRAY),
    ('', WHITE),
    ('PARA-DEBATE verdict: 5 agents lean BULL,', ACCENT2),
    ('but mandated BEAR challenge caps at HOLD+.', ACCENT2),
    ('', WHITE),
    ('Key watch: Services margin sustainability.', GOLD),
]
ty = y2 + 65
for text, color in lines:
    if text:
        draw.text((100, ty), text, font=f_small, fill=color)
    ty += 24

y3 = y2 + 420
draw.rounded_rectangle([60, y3, 340, y3+50], radius=10, fill=(15, 40, 60))
draw.text((80, y3+12), 'Real-time data', font=f_small, fill=ACCENT)
draw.rounded_rectangle([360, y3, 640, y3+50], radius=10, fill=(30, 15, 50))
draw.text((380, y3+12), 'Multi-agent RAG', font=f_small, fill=ACCENT2)
draw.rounded_rectangle([660, y3, 1020, y3+50], radius=10, fill=(20, 40, 20))
draw.text((680, y3+12), 'Sub-second response', font=f_small, fill=GREEN)

draw.text((60, H-60), 'NeuralQuant', font=f_label, fill=ACCENT)
draw.text((960, H-60), '5/8', font=f_small, fill=GRAY)
img.save('LOGOnq/slide_05.png', quality=95)
print('Slide 5 done')

# ============================================================
# Slide 6: Screener
# ============================================================
img = Image.new('RGB', (W, H), BG)
draw = ImageDraw.Draw(img)

draw.rectangle([0, 0, W, 90], fill=(23, 32, 48))
draw.text((40, 22), '06', font=f_big, fill=ACCENT)
draw.text((130, 30), 'AI STOCK SCREENER', font=f_title, fill=WHITE)
draw.text((130, 68), 'Find top-ranked stocks in seconds', font=f_small, fill=GRAY)

stocks = [
    ('GOOGL', 'Alphabet Inc', 10, GREEN, 'Quality 100%  Momentum 100%  Low Vol 100%'),
    ('XOM', 'Exxon Mobil', 9, GREEN, 'Value 100%  Low Vol 90%  Momentum 80%'),
    ('KEYS', 'Keysight Tech', 8, ACCENT, 'Quality 90%  Value 70%  Momentum 60%'),
    ('FDX', 'FedEx Corp', 7, ACCENT, 'Quality 80%  Momentum 60%  Insider 50%'),
    ('OXY', 'Occidental Pet', 6, ORANGE, 'Value 80%  Momentum 50%  Low Vol 40%'),
]

y = 120
for i, (ticker, name, score, color, drivers) in enumerate(stocks):
    card_y = y + i * 140
    draw.rounded_rectangle([60, card_y, 1020, card_y+120], radius=14, fill=DARK_CARD)
    cx, cy = 140, card_y + 60
    draw.ellipse([cx-35, cy-35, cx+35, cy+35], outline=color, width=3)
    draw.text((cx-18, cy-18), str(score), font=get_font(32, True), fill=color)
    draw.text((cx+5, cy-8), '/10', font=f_small, fill=GRAY)
    draw.text((210, card_y+20), ticker, font=get_font(28, True), fill=WHITE)
    draw.text((210, card_y+55), name, font=f_small, fill=GRAY)
    bar_x = 560
    bar_w = 380
    draw.rounded_rectangle([bar_x, card_y+30, bar_x+bar_w, card_y+50], radius=6, fill=(30, 40, 55))
    fill_w = int(bar_w * score / 10)
    draw.rounded_rectangle([bar_x, card_y+30, bar_x+fill_w, card_y+50], radius=6, fill=color)
    draw.text((210, card_y+85), drivers, font=f_small, fill=GRAY)

draw.text((60, H-60), 'NeuralQuant', font=f_label, fill=ACCENT)
draw.text((960, H-60), '6/8', font=f_small, fill=GRAY)
img.save('LOGOnq/slide_06.png', quality=95)
print('Slide 6 done')

# ============================================================
# Slide 7: India Coverage
# ============================================================
img = Image.new('RGB', (W, H), BG)
draw = ImageDraw.Draw(img)

draw.rectangle([0, 0, W, 90], fill=(23, 32, 48))
draw.text((40, 22), '07', font=f_big, fill=ACCENT)
draw.text((130, 30), 'INDIA MARKET COVERAGE', font=f_title, fill=WHITE)
draw.text((130, 68), 'NIFTY 50 + BSE analyzed with same AI depth', font=f_small, fill=GRAY)

draw.rectangle([0, 90, 8, 120], fill=(255, 153, 51))
draw.rectangle([0, 120, 8, 150], fill=(255, 255, 255))
draw.rectangle([0, 150, 8, 180], fill=(19, 136, 8))

y = 120
draw.rounded_rectangle([60, y, 1020, y+300], radius=16, fill=DARK_CARD)
draw.text((100, y+20), 'TCS  (Tata Consultancy Services)', font=get_font(26, True), fill=WHITE)
draw.text((100, y+55), 'NSE: TCS.NS  |  BSE: 532540', font=f_small, fill=GRAY)

factors = [('Quality', 90, GREEN), ('Value', 55, ORANGE), ('Momentum', 70, ACCENT),
           ('Low Vol', 85, GREEN), ('Insider', 50, GRAY)]
fx = 100
for fname, val, color in factors:
    fy = y + 95
    draw.text((fx, fy), fname, font=f_small, fill=GRAY)
    bar_y = fy + 25
    draw.rounded_rectangle([fx, bar_y, fx+140, bar_y+18], radius=5, fill=(30, 40, 55))
    fw = int(140 * val / 100)
    draw.rounded_rectangle([fx, bar_y, fx+fw, bar_y+18], radius=5, fill=color)
    draw.text((fx, bar_y+20), str(val) + '%', font=f_small, fill=color)
    fx += 170

draw.text((100, y+200), 'PARA-DEBATE: Mixed signals - quality strong, valuation', font=f_small, fill=ACCENT2)
draw.text((100, y+225), 'elevated. Adversarial flags IT sector rotation risk.', font=f_small, fill=ACCENT2)
draw.text((100, y+260), 'Verdict: HOLD (7/10)', font=get_font(20, True), fill=ORANGE)

y2 = y + 330
draw.rounded_rectangle([60, y2, 1020, y2+300], radius=16, fill=DARK_CARD)
draw.text((100, y2+20), 'RELIANCE  (Reliance Industries)', font=get_font(26, True), fill=WHITE)
draw.text((100, y2+55), 'NSE: RELIANCE.NS  |  BSE: 500325', font=f_small, fill=GRAY)

factors2 = [('Quality', 75, ACCENT), ('Value', 60, ORANGE), ('Momentum', 65, ACCENT),
            ('Low Vol', 80, GREEN), ('Insider', 45, GRAY)]
fx = 100
for fname, val, color in factors2:
    fy = y2 + 95
    draw.text((fx, fy), fname, font=f_small, fill=GRAY)
    bar_y = fy + 25
    draw.rounded_rectangle([fx, bar_y, fx+140, bar_y+18], radius=5, fill=(30, 40, 55))
    fw = int(140 * val / 100)
    draw.rounded_rectangle([fx, bar_y, fx+fw, bar_y+18], radius=5, fill=color)
    draw.text((fx, bar_y+20), str(val) + '%', font=f_small, fill=color)
    fx += 170

draw.text((100, y2+200), 'PARA-DEBATE: O2C + Retail growth vs refining margin', font=f_small, fill=ACCENT2)
draw.text((100, y2+225), 'compression. Geopolitical agent flags Middle East risk.', font=f_small, fill=ACCENT2)
draw.text((100, y2+260), 'Verdict: HOLD+ (6/10)', font=get_font(20, True), fill=ORANGE)

draw.text((60, H-60), 'NeuralQuant', font=f_label, fill=ACCENT)
draw.text((960, H-60), '7/8', font=f_small, fill=GRAY)
img.save('LOGOnq/slide_07.png', quality=95)
print('Slide 7 done')

# ============================================================
# Slide 8: CTA
# ============================================================
img = Image.new('RGB', (W, H), BG)
draw = ImageDraw.Draw(img)

for i in range(H):
    r = int(13 + (i/H) * 15)
    g = int(17 + (i/H) * 10)
    b = int(23 + (i/H) * 30)
    draw.line([(0, i), (W, i)], fill=(r, g, b))

cx, cy = W//2, 250
draw.ellipse([cx-120, cy-120, cx+120, cy+120], outline=ACCENT, width=4)
f_nq = get_font(80, True)
lw = text_width(draw, 'NQ', f_nq)
draw.text((cx - lw//2, cy-40), 'NQ', font=f_nq, fill=ACCENT)

f_try = get_font(48, True)
center_x(draw, 'Try NeuralQuant', f_try, 420, WHITE)

f_free = get_font(28, False)
center_x(draw, 'Free - No credit card', f_free, 480, GREEN)

# URL box centered
url_text = 'neuralquant.co'
f_url = get_font(32, True)
uw = text_width(draw, url_text, f_url)
box_w = uw + 60
box_x = (W - box_w) // 2
draw.rounded_rectangle([box_x, 540, box_x+box_w, 600], radius=14, fill=(20, 40, 60))
draw.text((box_x + 30, 553), url_text, font=f_url, fill=ACCENT)

features = [
    'Multi-Agent AI',
    '6-Factor Scoring',
    'AI Screener',
    'US + India',
]
tag_w, tag_h = 200, 70
pad = 20
total_w = len(features) * tag_w + (len(features) - 1) * pad
fx = (W - total_w) // 2
for label in features:
    draw.rounded_rectangle([fx, 660, fx+tag_w, 660+tag_h], radius=10, fill=DARK_CARD)
    lw = text_width(draw, label, f_small)
    draw.text((fx + (tag_w - lw)//2, 675), label, font=f_small, fill=WHITE)
    fx += tag_w + pad

center_x(draw, 'Free during development', f_body, 810, GOLD)
center_x(draw, 'NeuralQuant', f_label, H-60, ACCENT)
img.save('LOGOnq/slide_08.png', quality=95)
print('Slide 8 done')

# ============================================================
# Combine into PDF
# ============================================================
from PIL import Image as PILImage
slides = []
for i in range(1, 9):
    path = f'LOGOnq/slide_{i:02d}.png'
    s = PILImage.open(path).convert('RGB')
    slides.append(s)

pdf_path = 'LOGOnq/neuralquant_carousel.pdf'
slides[0].save(pdf_path, 'PDF', save_all=True, append_images=slides[1:], resolution=1080)
print(f'PDF saved: {pdf_path} ({len(slides)} slides)')
