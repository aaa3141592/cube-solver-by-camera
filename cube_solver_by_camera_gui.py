import cv2
import numpy as np
import kociemba
from PIL import Image, ImageDraw, ImageFont
import sys, os
import tkinter as tk
from tkinter import ttk, messagebox

try:
    from PIL import ImageTk
except ImportError:
    ImageTk = None

try:
    from pygrabber.dshow_graph import FilterGraph
except ImportError:
    FilterGraph = None

# --- 設定 ---
GRID_STEP = 60
CAPTURE_ORDER_CAPTURED = ["U","R","F","D","L","B"]
CAPTURE_ORDER_KOCIEMBA = ["U","R","F","D","L","B"]
CENTER_FIXED = {"U":"W", "R":"R", "F":"G", "D":"Y", "L":"O", "B":"B"}
# Kociembaの順序: U,R,F,D,L,B
SOLVED_CUBE = "W"*9 + "R"*9 + "G"*9 + "Y"*9 + "O"*9 + "B"*9

# 各面のキャプチャ時の向き指定
FACE_ORIENTATION = {
    "U": "White center on top, Green facing you",
    "F": "Green center facing you, White on top",
    "R": "Red center facing you, White on top",
    "B": "Blue center facing you, White on top",
    "L": "Orange center facing you, White on top",
    "D": "Yellow center on top, Green facing you",
}

def resource_path(filename):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(os.path.abspath("."), filename)

font_path = resource_path("msgothic.ttc")

# --- Pillowで日本語テキスト描画 ---
def put_japanese_text(frame, text, position, font_size=32, color=(255,255,255)):
    # OpenCV画像をPillow画像に変換
    img_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    # フォントパス（Windows標準のMSゴシックを使用）
    try:
        font = ImageFont.truetype(font_path, font_size)
    except:
        font = ImageFont.load_default()
    draw.text(position, text, font=font, fill=color)
    # Pillow画像をOpenCV画像に戻す
    frame[:,:] = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

# --- 色判定 ---
def get_color_label(h, s, v, central_color=None):
    """
    h: 0-179, s,v: 0-1
    central_color: 中央色で補正したい場合
    """
    if central_color:
        return central_color

    # 白判定
    if v > 0.85 and s < 0.25:
        return "W"
    # 暗い部分
    if v < 0.15:
        return "N"
    # オレンジ（赤より幅を広げる）
    if 8 <= h < 30 and s > 0.2:
        return "O"
    #赤
    if ((h < 8 or h > 160) and s > 0.35 and v > 0.3):
        return "R"
    # 黄
    if 20 <= h < 35 and s > 0.2:
        return "Y"
    # 緑
    if 35 <= h < 85 and s > 0.2:
        return "G"
    # 青
    if 85 <= h < 125 and s > 0.2:
        return "B"

    return "W"

# --- D面180°回転補正 ---
def rotate_face_180(face_str):
    """
    3x3面の9文字を180度回転（逆順）
    """
    if len(face_str) != 9:
        return face_str
    return face_str[::-1]

# --- キューブが揃っているか判定 ---
def is_cube_solved(cube_string):
    """
    キューブが揃っているか判定
    各面が同じ色で統一されているかチェック
    """
    if len(cube_string) != 54:
        return False
    
    # 各面が9文字ずつ
    faces = [cube_string[i:i+9] for i in range(0, 54, 9)]
    
    # 各面の9マスが全て同じ色かチェック
    for face in faces:
        if len(set(face)) != 1:  # 1種類の色でない
            return False
    
    return True

# --- キューブストリングの検証 ---
def validate_cube_string(cube_string):
    if len(cube_string) != 54:
        print(f"エラー: 長さが{len(cube_string)}文字です（54文字必要）")
        return False
    
    # 色のカウント
    color_counts = {}
    for color in cube_string:
        color_counts[color] = color_counts.get(color, 0) + 1
    
    # 不明色のチェック
    if 'N' in color_counts:
        print(f"エラー: 不明色(N)が{color_counts['N']}個含まれています")
        return False
    
    # 各色が9個ずつかチェック
    required_colors = ['W', 'R', 'G', 'B', 'O', 'Y']
    for color in required_colors:
        count = color_counts.get(color, 0)
        if count != 9:
            print(f"エラー: 色{color}が{count}個です（9個必要）")
            return False
    
    # 余分な色のチェック
    for color, count in color_counts.items():
        if color not in required_colors:
            print(f"エラー: 不正な色'{color}'が{count}個含まれています")
            return False
    
    return True

# --- 3x3 グリッドからラベル取得 ---
def sample_grid_labels(frame, cx, cy, step, current_face):
    labels=[]
    grid_size = step*2
    cell = grid_size//3
    
    temp_labels = []
    for i in range(3):
        for j in range(3):
            x = cx-step + j*cell
            y = cy-step + i*cell
            roi = frame[y:y+cell, x:x+cell]
            if roi.size==0:
                temp_labels.append("W")
                continue
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            h_med=float(np.median(hsv[:,:,0]))
            s_med=float(np.median(hsv[:,:,1]))/255.0
            v_med=float(np.median(hsv[:,:,2]))/255.0
            central_color=CENTER_FIXED[current_face] if (i==1 and j==1) else None
            label=get_color_label(h_med,s_med,v_med,central_color)
            temp_labels.append(label)
            
            # グリッド描画
            cv2.rectangle(frame,(x,y),(x+cell,y+cell),(0,255,0),2)
            
            # 文字色を背景に応じて調整
            if label in ['W', 'Y', 'O']:
                text_color = (0, 0, 0)  # 黒
            else:
                text_color = (255, 255, 255)  # 白
            
            cv2.putText(frame,label,(x+5,y+25),cv2.FONT_HERSHEY_SIMPLEX,0.8,text_color,2)
    
    labels = temp_labels
    
    return labels

# --- 半透明矢印描画 ---
def draw_transparent_arrow(frame, face, cx, cy):
    overlay = frame.copy()
    color=(0,0,255)
    thickness=3
    if face=="U": cv2.arrowedLine(overlay,(cx,cy+100),(cx,cy+50),color,thickness)
    elif face=="D": cv2.arrowedLine(overlay,(cx,cy-100),(cx,cy-50),color,thickness)
    elif face=="F": cv2.arrowedLine(overlay,(cx+50,cy),(cx-50,cy),color,thickness)
    elif face=="B": cv2.arrowedLine(overlay,(cx-50,cy),(cx+50,cy),color,thickness)
    elif face=="R": cv2.arrowedLine(overlay,(cx,cy-50),(cx,cy+50),color,thickness)
    elif face=="L": cv2.arrowedLine(overlay,(cx,cy+50),(cx,cy-50),color,thickness)
    alpha=0.5
    cv2.addWeighted(overlay,alpha,frame,1-alpha,0,frame)

# --- 回転方向を視覚的に表示 ---
def draw_rotation_guide(frame, move, cx, cy):
    """現在の手順の回転方向を矢印で表示"""
    # --- 一時的に何も描画しない ---
    pass

# --- 揃っている表示 ---
def draw_solved_message(frame):
    """キューブが揃っている場合のメッセージ表示"""
    overlay = frame.copy()
    h, w = frame.shape[:2]
    
    # 背景（半透明の緑）
    cv2.rectangle(overlay, (0, 0), (w, h), (0, 200, 0), -1)
    cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)
    
    # メインメッセージ（大きく）
    text1 = "ALREADY SOLVED!"
    text_size1 = cv2.getTextSize(text1, cv2.FONT_HERSHEY_SIMPLEX, 2.5, 5)[0]
    text_x1 = (w - text_size1[0]) // 2
    text_y1 = h // 2 - 80
    
    # 影
    cv2.putText(frame, text1, (text_x1+3, text_y1+3), 
               cv2.FONT_HERSHEY_SIMPLEX, 2.5, (0, 100, 0), 5)
    # メインテキスト
    cv2.putText(frame, text1, (text_x1, text_y1), 
               cv2.FONT_HERSHEY_SIMPLEX, 2.5, (255, 255, 255), 5)

    jp_text = "キューブはすでに揃っています！"
    put_japanese_text(frame, jp_text, (w//2-200, h//2+120), font_size=36, color=(255,255,255))
    
    # 操作説明
    sub_text = "Press 'r' to restart or 'q' to quit"
    sub_size = cv2.getTextSize(sub_text, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)[0]
    sub_x = (w - sub_size[0]) // 2
    sub_y = h - 50
    cv2.putText(frame, sub_text, (sub_x, sub_y), 
               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

# --- ソルブ画面用グリッド線描画 ---
def draw_solution_grid(frame, cx, cy, step):
    """ソルブ画面用の9マスグリッド線のみを描画（文字なし）"""
    grid_size = step * 2
    cell = grid_size // 3
    for i in range(3):
        for j in range(3):
            x = cx - step + j * cell
            y = cy - step + i * cell
            cv2.rectangle(frame, (x, y), (x + cell, y + cell), (0, 255, 0), 2)

def show_steps(frame, steps, current_step):
    # --- ソルブ時の左側にキューブの向きガイド ---
    # F/F'/B/B'でガイドの色を切り替え
    guide_face = "F"
    if current_step < len(steps):
        current_move = steps[current_step]
        if current_move in ["B", "B'", "B2", "B'2"]:
            guide_face = "B"
    draw_orientation_guide(frame, guide_face, 80, frame.shape[0]//2)
    """解法手順を表示（進捗とともに）"""
    # --- 上部進捗バー・手順表示・日本語説明・グリッド線 ---
    h, w = frame.shape[:2]
    cx, cy = w // 2, h // 2

    draw_solution_grid(frame, cx, cy, GRID_STEP)

    bar_width = int(w * 0.7)
    bar_x = (w - bar_width) // 2
    bar_y = 10
    bar_height = 18
    progress = (current_step + 1) / len(steps) if len(steps) > 0 else 0

    msg_y = bar_y + bar_height + 52
    msg_text = "画面をよく確認してください"
    try:
        font = ImageFont.truetype(font_path, 28)
    except:
        font = ImageFont.load_default()
    try:
        bbox = font.getbbox(msg_text)
        text_height = bbox[3] - bbox[1]
    except AttributeError:
        text_height = 28

    # 画面上端からメッセージテキスト下端までグレー背景
    gray_bottom = msg_y + text_height + 10  # 少し余白を追加
    cv2.rectangle(frame, (0, 0), (w, gray_bottom), (50, 50, 50), -1)

    # 進捗バー描画
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height), (100, 100, 100), -1)
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + int(bar_width * progress), bar_y + bar_height), (0, 255, 0), -1)
    progress_text = f"Step {current_step + 1} / {len(steps)}"
    text_size = cv2.getTextSize(progress_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
    text_x = bar_x + (bar_width - text_size[0]) // 2
    cv2.putText(frame, progress_text, (text_x, bar_y + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    # 手順名（小さめ表示）
    if current_step < len(steps):
        current_move = steps[current_step]
        step_text = f"Step: {current_move}"
        step_size = cv2.getTextSize(step_text, cv2.FONT_HERSHEY_SIMPLEX, 1.1, 3)[0]
        step_x = (w - step_size[0]) // 2
        cv2.putText(frame, step_text, (step_x, bar_y + bar_height + 28), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 255, 255), 3)
        
        text_width = bbox[2] - bbox[0] if 'bbox' in locals() else 28 * len(msg_text)
        center_x = (w - text_width) // 2
        put_japanese_text(frame, msg_text, (center_x, msg_y), font_size=28, color=(0,255,255))

    # グリッド内部に回転方向を示す矢印（U/U'のみ）
    if current_step < len(steps):
        current_move = steps[current_step]
        # グリッド上段中央3マスに収まるように矢印座標を調整
        grid_size = GRID_STEP * 2
        cell = grid_size // 3
        # 上段中央3マスの範囲
        top_y = cy - GRID_STEP
        center_y = top_y + cell // 2
        left_x = cx - cell
        center_x = cx
        right_x = cx + cell
        if current_move == "U":
            # 左向き矢印（右→左）
            arrow_start = (right_x, center_y)
            arrow_end = (left_x, center_y)
            cv2.arrowedLine(frame, arrow_start, arrow_end, (0, 0, 255), 6, tipLength=0.3)
        elif current_move == "U":
            # 左向き矢印（右→左）
            arrow_start = (right_x, center_y)
            arrow_end = (left_x, center_y)
            cv2.arrowedLine(frame, arrow_start, arrow_end, (0, 0, 255), 6, tipLength=0.3)
        elif current_move == "U2":
            # 左向き矢印（右→左）
            arrow_start = (right_x, center_y)
            arrow_end = (left_x, center_y)
            cv2.arrowedLine(frame, arrow_start, arrow_end, (0, 0, 255), 6, tipLength=0.3)
            # "180°" を矢印終点の少し下にPillowで描画
            put_japanese_text(frame, "180°", (arrow_end[0]-20, arrow_end[1]+20), font_size=32, color=(164, 61, 127))

        elif current_move == "U'":
            # 右向き矢印（左→右）
            arrow_start = (left_x, center_y)
            arrow_end = (right_x, center_y)
            cv2.arrowedLine(frame, arrow_start, arrow_end, (0, 0, 255), 6, tipLength=0.3)
        elif current_move == "U'2":
            # 右向き矢印（左→右）
            arrow_start = (left_x, center_y)
            arrow_end = (right_x, center_y)
            cv2.arrowedLine(frame, arrow_start, arrow_end, (0, 0, 255), 6, tipLength=0.3)
            put_japanese_text(frame, "180°", (arrow_end[0]-20, arrow_end[1]+20), font_size=32, color=(164, 61, 127))

        elif current_move == "D":
            # Dは下段中央3マスに右向き矢印
            bottom_y = cy + GRID_STEP
            center_y_d = bottom_y - cell // 2
            arrow_start = (left_x, center_y_d)
            arrow_end = (right_x, center_y_d)
            cv2.arrowedLine(frame, arrow_start, arrow_end, (0, 0, 255), 6, tipLength=0.3)
        elif current_move == "D2":
            # Dは下段中央3マスに右向き矢印
            bottom_y = cy + GRID_STEP
            center_y_d = bottom_y - cell // 2
            arrow_start = (left_x, center_y_d)
            arrow_end = (right_x, center_y_d)
            cv2.arrowedLine(frame, arrow_start, arrow_end, (0, 0, 255), 6, tipLength=0.3)
            put_japanese_text(frame, "180°", (arrow_end[0]-20, arrow_end[1]+20), font_size=32, color=(164, 61, 127))

        elif current_move == "D'":
            # D'は下段中央3マスに左向き矢印
            bottom_y = cy + GRID_STEP
            center_y_d = bottom_y - cell // 2
            arrow_start = (right_x, center_y_d)
            arrow_end = (left_x, center_y_d)
            cv2.arrowedLine(frame, arrow_start, arrow_end, (0, 0, 255), 6, tipLength=0.3)
        elif current_move == "D'2":
            # D'は下段中央3マスに左向き矢印
            bottom_y = cy + GRID_STEP
            center_y_d = bottom_y - cell // 2
            arrow_start = (right_x, center_y_d)
            arrow_end = (left_x, center_y_d)
            cv2.arrowedLine(frame, arrow_start, arrow_end, (0, 0, 255), 6, tipLength=0.3)
            put_japanese_text(frame, "180°", (arrow_end[0]-20, arrow_end[1]+20), font_size=32, color=(164, 61, 127))

        elif current_move == "R":
            # Rは右側縦3マスに上向き矢印
            right_col_x = cx + GRID_STEP-20
            top_y_r = cy - cell
            bottom_y_r = cy + cell
            arrow_start = (right_col_x, bottom_y_r)
            arrow_end = (right_col_x, top_y_r)
            cv2.arrowedLine(frame, arrow_start, arrow_end, (0, 0, 255), 6, tipLength=0.3)
        elif current_move == "R2":
            # Rは右側縦3マスに上向き矢印
            right_col_x = cx + GRID_STEP-20
            top_y_r = cy - cell
            bottom_y_r = cy + cell
            arrow_start = (right_col_x, bottom_y_r)
            arrow_end = (right_col_x, top_y_r)
            cv2.arrowedLine(frame, arrow_start, arrow_end, (0, 0, 255), 6, tipLength=0.3)
            put_japanese_text(frame, "180°", (arrow_end[0]+10, arrow_end[1]-40), font_size=32, color=(164, 61, 127))
        elif current_move == "R'":
            # R'は右側縦3マスに下向き矢印
            right_col_x = cx + GRID_STEP-20
            top_y_r = cy - cell
            bottom_y_r = cy + cell
            arrow_start = (right_col_x, top_y_r)
            arrow_end = (right_col_x, bottom_y_r)
            cv2.arrowedLine(frame, arrow_start, arrow_end, (0, 0, 255), 6, tipLength=0.3)
        elif current_move == "R'2":
            # R'は右側縦3マスに下向き矢印
            right_col_x = cx + GRID_STEP-20
            top_y_r = cy - cell
            bottom_y_r = cy + cell
            arrow_start = (right_col_x, top_y_r)
            arrow_end = (right_col_x, bottom_y_r)
            cv2.arrowedLine(frame, arrow_start, arrow_end, (0, 0, 255), 6, tipLength=0.3)
            put_japanese_text(frame, "180°", (arrow_end[0]+10, arrow_end[1]+10), font_size=32, color=(164, 61, 127))
        elif current_move == "L":
            # Lは左側縦3マスに下向き矢印
            left_col_x = cx - GRID_STEP+20
            top_y_l = cy - cell
            bottom_y_l = cy + cell
            arrow_start = (left_col_x, top_y_l)
            arrow_end = (left_col_x, bottom_y_l)
            cv2.arrowedLine(frame, arrow_start, arrow_end, (0, 0, 255), 6, tipLength=0.3)
        elif current_move == "L2":
            # Lは左側縦3マスに下向き矢印
            left_col_x = cx - GRID_STEP+20
            top_y_l = cy - cell
            bottom_y_l = cy + cell
            arrow_start = (left_col_x, top_y_l)
            arrow_end = (left_col_x, bottom_y_l)
            cv2.arrowedLine(frame, arrow_start, arrow_end, (0, 0, 255), 6, tipLength=0.3)
            put_japanese_text(frame, "180°", (arrow_end[0]-40, arrow_end[1]+10), font_size=32, color=(164, 61, 127))
        elif current_move == "L'":
            # L'は左側縦3マスに上向き矢印
            left_col_x = cx - GRID_STEP+20
            top_y_l = cy - cell
            bottom_y_l = cy + cell
            arrow_start = (left_col_x, bottom_y_l)
            arrow_end = (left_col_x, top_y_l)
            cv2.arrowedLine(frame, arrow_start, arrow_end, (0, 0, 255), 6, tipLength=0.3)
        elif current_move == "L'2":
            # L'は左側縦3マスに上向き矢印
            left_col_x = cx - GRID_STEP+20
            top_y_l = cy - cell
            bottom_y_l = cy + cell
            arrow_start = (left_col_x, bottom_y_l)
            arrow_end = (left_col_x, top_y_l)
            cv2.arrowedLine(frame, arrow_start, arrow_end, (0, 0, 255), 6, tipLength=0.3)
            # 180度の文字を見やすく表示（白半透明背景＋赤太字）
            bg_x = arrow_end[0]-55
            bg_y = arrow_end[1]-45
            bg_w = 80
            bg_h = 45
            overlay = frame.copy()
            cv2.rectangle(overlay, (bg_x, bg_y), (bg_x+bg_w, bg_y+bg_h), (255,255,255), -1)
            cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
            put_japanese_text(frame, "180°", (arrow_end[0]-40, arrow_end[1]-10), font_size=38, color=(164, 61, 127))
            
        elif current_move == "F":
            # Fのライン・矢印を赤色で描画（下段の接続ルール反映）
            grid_size = GRID_STEP * 2
            cell = grid_size // 3
            color = (0,0,255)  # 赤色（BGR）
            thickness = 6
            y_top = cy - cell
            x_left = cx - cell
            x_mid = cx
            x_right = cx + cell
            y_mid = cy
            y_bottom = cy + cell
            cv2.line(frame, (x_left, y_top), (x_right, y_top), color, thickness)
            cv2.line(frame, (x_left, y_top), (x_left, y_mid), color, thickness)
            cv2.line(frame, (x_right, y_top), (x_right, y_mid), color, thickness)
            cv2.line(frame, (x_left, y_bottom), (x_mid, y_bottom), color, thickness)
            cv2.line(frame, (x_left, y_bottom), (x_left, y_mid), color, thickness)
            cv2.line(frame, (x_right, y_mid), (x_right, y_bottom), color, thickness)
            arrow_start = (x_right, y_bottom)
            arrow_end = (x_right, y_bottom + cell//2)
            cv2.arrowedLine(frame, arrow_start, arrow_end, color, thickness, tipLength=0.3)
        elif current_move == "F2":
            grid_size = GRID_STEP * 2
            cell = grid_size // 3
            color = (0,0,255)
            thickness = 6
            y_top = cy - cell
            x_left = cx - cell
            x_mid = cx
            x_right = cx + cell
            y_mid = cy
            y_bottom = cy + cell
            cv2.line(frame, (x_left, y_top), (x_right, y_top), color, thickness)
            cv2.line(frame, (x_left, y_top), (x_left, y_mid), color, thickness)
            cv2.line(frame, (x_right, y_top), (x_right, y_mid), color, thickness)
            cv2.line(frame, (x_left, y_bottom), (x_mid, y_bottom), color, thickness)
            cv2.line(frame, (x_left, y_bottom), (x_left, y_mid), color, thickness)
            cv2.line(frame, (x_right, y_mid), (x_right, y_bottom), color, thickness)
            arrow_start = (x_right, y_bottom)
            arrow_end = (x_right, y_bottom + cell//2)
            cv2.arrowedLine(frame, arrow_start, arrow_end, color, thickness, tipLength=0.3)
            put_japanese_text(frame, "180°", (arrow_end[0]-40, arrow_end[1]-40), font_size=32, color=(164, 61, 127))
        elif current_move == "F'":
            grid_size = GRID_STEP * 2
            cell = grid_size // 3
            color = (0,0,255)
            thickness = 6
            y_top = cy - cell
            x_left = cx - cell
            x_mid = cx
            x_right = cx + cell
            y_mid = cy
            y_bottom = cy + cell
            cv2.line(frame, (x_right, y_top), (x_left, y_top), color, thickness)
            cv2.line(frame, (x_right, y_top), (x_right, y_mid), color, thickness)
            cv2.line(frame, (x_left, y_top), (x_left, y_mid), color, thickness)
            cv2.line(frame, (x_right, y_bottom), (x_mid, y_bottom), color, thickness)
            cv2.line(frame, (x_right, y_bottom), (x_right, y_mid), color, thickness)
            cv2.line(frame, (x_left, y_mid), (x_left, y_bottom), color, thickness)
            arrow_start = (x_left, y_bottom)
            arrow_end = (x_left, y_bottom + cell//2)
            cv2.arrowedLine(frame, arrow_start, arrow_end, color, thickness, tipLength=0.3)
        elif current_move == "F'2":
            grid_size = GRID_STEP * 2
            cell = grid_size // 3
            color = (0,0,255)
            thickness = 6
            y_top = cy - cell
            x_left = cx - cell
            x_mid = cx
            x_right = cx + cell
            y_mid = cy
            y_bottom = cy + cell
            cv2.line(frame, (x_left, y_top), (x_right, y_top), color, thickness)
            cv2.line(frame, (x_left, y_top), (x_left, y_mid), color, thickness)
            cv2.line(frame, (x_right, y_top), (x_right, y_mid), color, thickness)
            cv2.line(frame, (x_left, y_bottom), (x_mid, y_bottom), color, thickness)
            cv2.line(frame, (x_left, y_bottom), (x_left, y_mid), color, thickness)
            cv2.line(frame, (x_right, y_mid), (x_right, y_bottom), color, thickness)
            arrow_start = (x_right, y_bottom - cell//2)
            arrow_end = (x_right, y_bottom)
            cv2.arrowedLine(frame, arrow_start, arrow_end, color, thickness, tipLength=0.3)
            put_japanese_text(frame, "180°", (arrow_end[0]-40, arrow_end[1]-40), font_size=32, color=(164, 61, 127))
        elif current_move == "B":
            # BはFの描画ロジックを使う
            grid_size = GRID_STEP * 2
            cell = grid_size // 3
            color = (0,0,255)  # 赤色（BGR）
            thickness = 6
            y_top = cy - cell
            x_left = cx - cell
            x_mid = cx
            x_right = cx + cell
            y_mid = cy
            y_bottom = cy + cell
            cv2.line(frame, (x_left, y_top), (x_right, y_top), color, thickness)
            cv2.line(frame, (x_left, y_top), (x_left, y_mid), color, thickness)
            cv2.line(frame, (x_right, y_top), (x_right, y_mid), color, thickness)
            cv2.line(frame, (x_left, y_bottom), (x_mid, y_bottom), color, thickness)
            cv2.line(frame, (x_left, y_bottom), (x_left, y_mid), color, thickness)
            cv2.line(frame, (x_right, y_mid), (x_right, y_bottom), color, thickness)
            arrow_start = (x_right, y_bottom)
            arrow_end = (x_right, y_bottom + cell//2)
            cv2.arrowedLine(frame, arrow_start, arrow_end, color, thickness, tipLength=0.3)
        elif current_move == "B2":
            # B2はF'2の描画ロジックを使う
            grid_size = GRID_STEP * 2
            cell = grid_size // 3
            color = (0,0,255)
            thickness = 6
            y_top = cy - cell
            x_left = cx - cell
            x_mid = cx
            x_right = cx + cell
            y_mid = cy
            y_bottom = cy + cell
            cv2.line(frame, (x_left, y_top), (x_right, y_top), color, thickness)
            cv2.line(frame, (x_left, y_top), (x_left, y_mid), color, thickness)
            cv2.line(frame, (x_right, y_top), (x_right, y_mid), color, thickness)
            cv2.line(frame, (x_left, y_bottom), (x_mid, y_bottom), color, thickness)
            cv2.line(frame, (x_left, y_bottom), (x_left, y_mid), color, thickness)
            cv2.line(frame, (x_right, y_mid), (x_right, y_bottom), color, thickness)
            arrow_start = (x_right, y_bottom - cell//2)
            arrow_end = (x_right, y_bottom)
            cv2.arrowedLine(frame, arrow_start, arrow_end, color, thickness, tipLength=0.3)
            put_japanese_text(frame, "180°", (arrow_end[0]-40, arrow_end[1]-40), font_size=32, color=(164, 61, 127))
        elif current_move == "B'":
            # B'はF'の描画ロジックを使う
            grid_size = GRID_STEP * 2
            cell = grid_size // 3
            color = (0,0,255)
            thickness = 6
            y_top = cy - cell
            x_left = cx - cell
            x_mid = cx
            x_right = cx + cell
            y_mid = cy
            y_bottom = cy + cell
            cv2.line(frame, (x_right, y_top), (x_left, y_top), color, thickness)
            cv2.line(frame, (x_right, y_top), (x_right, y_mid), color, thickness)
            cv2.line(frame, (x_left, y_top), (x_left, y_mid), color, thickness)
            cv2.line(frame, (x_right, y_bottom), (x_mid, y_bottom), color, thickness)
            cv2.line(frame, (x_right, y_bottom), (x_right, y_mid), color, thickness)
            cv2.line(frame, (x_left, y_mid), (x_left, y_bottom), color, thickness)
            arrow_start = (x_left, y_bottom)
            arrow_end = (x_left, y_bottom + cell//2)
            cv2.arrowedLine(frame, arrow_start, arrow_end, color, thickness, tipLength=0.3)
        elif current_move == "B'2":
            # B'2はF2の描画ロジックを使う
            grid_size = GRID_STEP * 2
            cell = grid_size // 3
            color = (0,0,255)
            thickness = 6
            y_top = cy - cell
            x_left = cx - cell
            x_mid = cx
            x_right = cx + cell
            y_mid = cy
            y_bottom = cy + cell
            cv2.line(frame, (x_left, y_top), (x_right, y_top), color, thickness)
            cv2.line(frame, (x_left, y_top), (x_left, y_mid), color, thickness)
            cv2.line(frame, (x_right, y_top), (x_right, y_mid), color, thickness)
            cv2.line(frame, (x_left, y_bottom), (x_mid, y_bottom), color, thickness)
            cv2.line(frame, (x_left, y_bottom), (x_left, y_mid), color, thickness)
            cv2.line(frame, (x_right, y_mid), (x_right, y_bottom), color, thickness)
            arrow_start = (x_right, y_bottom)
            arrow_end = (x_right, y_bottom + cell//2)
            cv2.arrowedLine(frame, arrow_start, arrow_end, color, thickness, tipLength=0.3)
            put_japanese_text(frame, "180°", (arrow_end[0]-40, arrow_end[1]-40), font_size=32, color=(164, 61, 127))

    # 回転ガイド表示
    draw_rotation_guide(frame, current_move, frame.shape[1]//2, frame.shape[0]//2)

    # 次の手順のプレビュー（下部左）
    if current_step + 1 < len(steps):
        next_move = steps[current_step + 1]
        cv2.putText(frame, f"Next: {next_move}", (30, frame.shape[0] - 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (200, 200, 200), 2)

    # 操作説明（下部中央）背景グレー
    help_text = "Press ENTER to continue"
    help_size = cv2.getTextSize(help_text, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)[0]
    help_x = (frame.shape[1] - help_size[0]) // 2
    # グレー背景（高さ40px）
    cv2.rectangle(frame, (0, frame.shape[0] - 45), (frame.shape[1], frame.shape[0]), (50, 50, 50), -1)
    cv2.putText(frame, help_text, (help_x, frame.shape[0] - 15), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 0), 2)

# --- キャプチャ画面の表示強化 ---
def draw_capture_ui(frame, current_face, face_number, guide_text):
    """キャプチャ中のUI表示"""
    h, w = frame.shape[:2]
    
    # 上部バー（進捗表示）
    cv2.rectangle(frame, (0, 0), (w, 130), (40, 40, 40), -1)
    
    # 進捗バー
    total_faces = 6
    progress = face_number / total_faces
    bar_width = int(w * 0.6)
    bar_x = (w - bar_width) // 2
    bar_y = 15
    bar_height = 20
    
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height), 
                 (80, 80, 80), -1)
    cv2.rectangle(frame, (bar_x, bar_y), 
                 (bar_x + int(bar_width * progress), bar_y + bar_height), 
                 (0, 200, 255), -1)
    
    # 進捗テキスト
    progress_text = f"Face {face_number} / 6"
    text_size = cv2.getTextSize(progress_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
    text_x = bar_x + (bar_width - text_size[0]) // 2
    cv2.putText(frame, progress_text, (text_x, bar_y + 15), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    # ガイドテキスト（メイン）
    guide = guide_text[current_face]
    guide_size = cv2.getTextSize(guide, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)[0]
    guide_x = (w - guide_size[0]) // 2
    cv2.putText(frame, guide, (guide_x, 60), 
               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    
    # 向き指定（詳細説明）
    orientation = FACE_ORIENTATION[current_face]
    orient_size = cv2.getTextSize(orientation, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)[0]
    orient_x = (w - orient_size[0]) // 2
    cv2.putText(frame, orientation, (orient_x, 90), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
    
    # 面の色情報
    color_map_text = {
        "W": "White", "R": "Red", "G": "Green", 
        "B": "Blue", "O": "Orange", "Y": "Yellow"
    }
    color_full = color_map_text.get(CENTER_FIXED[current_face], CENTER_FIXED[current_face])
    color_text = f"Center: {color_full}"
    color_size = cv2.getTextSize(color_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
    color_x = (w - color_size[0]) // 2
    cv2.putText(frame, color_text, (color_x, 115), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
    
    # 下部：操作説明
    cv2.rectangle(frame, (0, h - 50), (w, h), (40, 40, 40), -1)
    help_text = "Press ENTER to capture this face"
    help_size = cv2.getTextSize(help_text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
    help_x = (w - help_size[0]) // 2
    cv2.putText(frame, help_text, (help_x, h - 20), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

# --- 色マッピング ---
COLOR_MAP = {
    "W": (255, 255, 255),  # 白
    "R": (0, 0, 255),      # 赤
    "G": (0, 255, 0),      # 緑
    "B": (255, 0, 0),      # 青
    "O": (0, 165, 255),    # オレンジ
    "Y": (0, 255, 255),    # 黄
    "N": (100, 100, 100),  # 不明
}

# --- 展開図描画 ---
def draw_cube_net(frame, collected_faces, current_capturing_face=None):
    """
    キューブの展開図を描画（右上に小さく）
    
    展開図レイアウト:
           [U]
       [L] [F] [R] [B]
           [D]
    """
    # 展開図の位置とサイズ
    cell_size = 15
    margin = 10
    start_x = frame.shape[1] - 12 * cell_size - margin
    start_y = margin + 140
    
    # 背景
    bg_width = 12 * cell_size + 10
    bg_height = 13 * cell_size + 10  # 高さを拡大（従来9→13）
    overlay = frame.copy()
    cv2.rectangle(overlay, (start_x - 5, start_y - 20), 
                 (start_x + bg_width, start_y + bg_height), 
                 (40, 40, 40), -1)
    cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)
    
    # タイトル
    cv2.putText(frame, "Cube Net", (start_x, start_y - 5), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    # 展開図の各面の位置定義
    face_positions = {
        "U": (3, 0),  # 上面
        "L": (0, 3),  # 左面
        "F": (3, 3),  # 前面
        "R": (6, 3),  # 右面
        "B": (9, 3),  # 後面
        "D": (3, 6),  # 下面
    }
    
    # 各面を描画
    for face_name, (face_x, face_y) in face_positions.items():
        # 面の色データを取得
        if face_name in collected_faces:
            face_colors = collected_faces[face_name]
        else:
            face_colors = "N" * 9  # 未キャプチャは灰色
        
        # 3x3のセルを描画
        for i in range(3):
            for j in range(3):
                cell_x = start_x + (face_x + j) * cell_size
                cell_y = start_y + (face_y + i) * cell_size
                
                # 色を取得
                color_label = face_colors[i * 3 + j]
                color = COLOR_MAP.get(color_label, (100, 100, 100))
                
                # セルを描画
                cv2.rectangle(frame, (cell_x, cell_y), 
                            (cell_x + cell_size - 2, cell_y + cell_size - 2), 
                            color, -1)
                
                # 枠線
                border_color = (150, 150, 150)
                if face_name == current_capturing_face:
                    border_color = (0, 255, 0)  # キャプチャ中の面は緑
                cv2.rectangle(frame, (cell_x, cell_y), 
                            (cell_x + cell_size - 2, cell_y + cell_size - 2), 
                            border_color, 1)
        
        # 面のラベル（中央に小さく表示）
        label_x = start_x + (face_x + 1) * cell_size + cell_size // 4 - 2
        label_y = start_y + (face_y + 1) * cell_size + cell_size // 2 + 3
        label_color = (0, 0, 0) if face_name in collected_faces else (150, 150, 150)
        cv2.putText(frame, face_name, (label_x, label_y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.3, label_color, 1)

# --- 大きな展開図描画（解法中用） ---
def draw_large_cube_net(frame, collected_faces):
    """
    画面左側に大きな展開図を描画
    """
    cell_size = 25
    margin = 20
    start_x = margin
    start_y = 200
    
    # 背景
    bg_width = 12 * cell_size + 20
    bg_height = 9 * cell_size + 20
    overlay = frame.copy()
    cv2.rectangle(overlay, (start_x - 10, start_y - 30), 
                 (start_x + bg_width, start_y + bg_height), 
                 (30, 30, 30), -1)
    cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)
    
    # タイトル
    cv2.putText(frame, "Current State", (start_x, start_y - 10), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    # 展開図の各面の位置定義
    face_positions = {
        "U": (3, 0),
        "L": (0, 3),
        "F": (3, 3),
        "R": (6, 3),
        "B": (9, 3),
        "D": (3, 6),
    }
    
    # 各面を描画
    for face_name, (face_x, face_y) in face_positions.items():
        if face_name not in collected_faces:
            continue
        face_colors = collected_faces[face_name]
        
        # 3x3のセルを描画
        for i in range(3):
            for j in range(3):
                cell_x = start_x + (face_x + j) * cell_size
                cell_y = start_y + (face_y + i) * cell_size
                
                color_label = face_colors[i * 3 + j]
                color = COLOR_MAP.get(color_label, (100, 100, 100))
                
                # セルを描画
                cv2.rectangle(frame, (cell_x, cell_y), 
                            (cell_x + cell_size - 2, cell_y + cell_size - 2), 
                            color, -1)
                
                # 黒い枠線
                cv2.rectangle(frame, (cell_x, cell_y), 
                            (cell_x + cell_size - 2, cell_y + cell_size - 2), 
                            (0, 0, 0), 1)
        
        # 面のラベル
        label_x = start_x + (face_x + 1) * cell_size + cell_size // 4
        label_y = start_y + (face_y + 1) * cell_size + cell_size // 2 + 5
        cv2.putText(frame, face_name, (label_x, label_y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)

# --- 向き指定のビジュアルガイド ---
def draw_orientation_guide(frame, current_face, cx, cy):
    """キューブの向きを視覚的に示すガイド"""
    guide_size = 100
    guide_x = 30
    guide_y = frame.shape[0] // 2 - guide_size // 2
    
    # 背景
    overlay = frame.copy()
    cv2.rectangle(overlay, (guide_x - 10, guide_y - 30), 
                 (guide_x + guide_size + 10, guide_y + guide_size + 40), 
                 (30, 30, 30), -1)
    cv2.addWeighted(overlay, 0.8, frame, 0.2, 0, frame)
    
    # タイトル
    cv2.putText(frame, "Orientation", (guide_x - 5, guide_y - 10), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    # 簡易キューブ描画（3D風）
    cube_size = guide_size
    
    # 中央の面（正面）
    center_color = COLOR_MAP.get(CENTER_FIXED[current_face], (150, 150, 150))
    cv2.rectangle(frame, (guide_x + 10, guide_y + 10), 
                 (guide_x + cube_size - 10, guide_y + cube_size - 10), 
                 center_color, -1)
    cv2.rectangle(frame, (guide_x + 10, guide_y + 10), 
                 (guide_x + cube_size - 10, guide_y + cube_size - 10), 
                 (255, 255, 255), 2)
    
    # 面のラベル
    cv2.putText(frame, current_face, (guide_x + cube_size // 2 - 10, guide_y + cube_size // 2 + 10), 
               cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 3)
    
    # 上面の色ヒント（U面とD面以外）
    if current_face not in ["U", "D"]:
        top_color = COLOR_MAP.get("W", (255, 255, 255))  # 白が上
        # 上部の小さな面
        cv2.fillPoly(frame, [np.array([
            [guide_x + 10, guide_y + 10],
            [guide_x + cube_size - 10, guide_y + 10],
            [guide_x + cube_size - 5, guide_y + 5],
            [guide_x + 15, guide_y + 5]
        ])], top_color)
        cv2.polylines(frame, [np.array([
            [guide_x + 10, guide_y + 10],
            [guide_x + cube_size - 10, guide_y + 10],
            [guide_x + cube_size - 5, guide_y + 5],
            [guide_x + 15, guide_y + 5]
        ])], True, (255, 255, 255), 2)
        
        # "WHITE" ラベル
        cv2.putText(frame, "W", (guide_x + cube_size // 2 - 5, guide_y + 8), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
    
    # U面の場合：前面に緑のヒント
    if current_face == "U":
        front_color = COLOR_MAP.get("G", (0, 255, 0))
        cv2.fillPoly(frame, [np.array([
            [guide_x + 10, guide_y + cube_size - 10],
            [guide_x + cube_size - 10, guide_y + cube_size - 10],
            [guide_x + cube_size - 5, guide_y + cube_size - 5],
            [guide_x + 15, guide_y + cube_size - 5]
        ])], front_color)
        cv2.polylines(frame, [np.array([
            [guide_x + 10, guide_y + cube_size - 10],
            [guide_x + cube_size - 10, guide_y + cube_size - 10],
            [guide_x + cube_size - 5, guide_y + cube_size - 5],
            [guide_x + 15, guide_y + cube_size - 5]
        ])], True, (255, 255, 255), 2)
        cv2.putText(frame, "G", (guide_x + cube_size // 2 - 5, guide_y + cube_size - 12), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
    
    # D面の場合：前面に緑のヒント
    if current_face == "D":
        front_color = COLOR_MAP.get("G", (0, 255, 0))
        cv2.fillPoly(frame, [np.array([
            [guide_x + 10, guide_y + cube_size - 10],
            [guide_x + cube_size - 10, guide_y + cube_size - 10],
            [guide_x + cube_size - 5, guide_y + cube_size - 5],
            [guide_x + 15, guide_y + cube_size - 5]
        ])], front_color)
        cv2.polylines(frame, [np.array([
            [guide_x + 10, guide_y + cube_size - 10],
            [guide_x + cube_size - 10, guide_y + cube_size - 10],
            [guide_x + cube_size - 5, guide_y + cube_size - 5],
            [guide_x + 15, guide_y + cube_size - 5]
        ])], True, (255, 255, 255), 2)
        cv2.putText(frame, "G", (guide_x + cube_size // 2 - 5, guide_y + cube_size - 12), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
# --- 色編集モード用の変数 ---
edit_mode = False
selected_face = None
selected_cell = None
color_palette = ['W', 'R', 'G', 'B', 'O', 'Y']
current_palette_index = 0
collected_faces_global = {}

# --- パレット描画 ---
def draw_color_palette(frame):
    """色選択パレットを描画"""
    h, w = frame.shape[:2]
    palette_y = h - 100
    palette_x = w // 2 - 200
    cell_size = 50
    
    # 背景
    overlay = frame.copy()
    cv2.rectangle(overlay, (palette_x - 10, palette_y - 35), 
                 (palette_x + len(color_palette) * (cell_size + 10), palette_y + cell_size + 10), 
                 (40, 40, 40), -1)
    cv2.addWeighted(overlay, 0.9, frame, 0.1, 0, frame)
    
    # タイトル
    cv2.putText(frame, "Color Palette (Click)", 
               (palette_x, palette_y - 15), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    # 各色を描画
    for i, color_label in enumerate(color_palette):
        x = palette_x + i * (cell_size + 10)
        color = COLOR_MAP[color_label]
        
        # セル描画
        cv2.rectangle(frame, (x, palette_y), 
                     (x + cell_size, palette_y + cell_size), 
                     color, -1)
        
        # 選択中の色を強調
        border_color = (0, 255, 255) if i == current_palette_index else (200, 200, 200)
        border_thickness = 4 if i == current_palette_index else 2
        cv2.rectangle(frame, (x, palette_y), 
                     (x + cell_size, palette_y + cell_size), 
                     border_color, border_thickness)
        
        # ラベル
        text_color = (0, 0, 0) if color_label in ['W', 'Y', 'O'] else (255, 255, 255)
        cv2.putText(frame, color_label, 
                   (x + cell_size // 2 - 8, palette_y + cell_size // 2 + 8), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, text_color, 2)
    
    return palette_x, palette_y, cell_size

# --- 編集可能な展開図描画 ---
def draw_editable_cube_net(frame, collected_faces):
    """
    編集可能なキューブ展開図を描画
    """
    h, w = frame.shape[:2]
    cell_size = 30
    start_x = w // 2 - 6 * cell_size
    start_y = 80
    
    # 背景
    bg_width = 12 * cell_size + 20
    bg_height = 9 * cell_size + 20
    overlay = frame.copy()
    cv2.rectangle(overlay, (start_x - 10, start_y - 50), 
                 (start_x + bg_width, start_y + bg_height), 
                 (30, 30, 30), -1)
    cv2.addWeighted(overlay, 0.9, frame, 0.1, 0, frame)
    
    # タイトル
    title_text = "Edit Colors - Click cells to select, then click palette"
    cv2.putText(frame, title_text, 
               (start_x - 10, start_y - 25), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
    
    # 展開図の各面の位置定義
    face_positions = {
        "U": (3, 0),
        "L": (0, 3),
        "F": (3, 3),
        "R": (6, 3),
        "B": (9, 3),
        "D": (3, 6),
    }
    
    # 各面を描画
    for face_name, (face_x, face_y) in face_positions.items():
        if face_name not in collected_faces:
            continue
            
        face_colors = collected_faces[face_name]
        
        # 3x3のセルを描画
        for i in range(3):
            for j in range(3):
                cell_x = start_x + (face_x + j) * cell_size
                cell_y = start_y + (face_y + i) * cell_size
                cell_index = i * 3 + j
                
                color_label = face_colors[cell_index]
                color = COLOR_MAP.get(color_label, (100, 100, 100))
                
                # セルを描画
                cv2.rectangle(frame, (cell_x, cell_y), 
                            (cell_x + cell_size - 2, cell_y + cell_size - 2), 
                            color, -1)
                
                # 選択中のセルを強調
                if selected_face == face_name and selected_cell == cell_index:
                    border_color = (0, 255, 255)
                    border_thickness = 3
                else:
                    border_color = (0, 0, 0)
                    border_thickness = 1
                
                cv2.rectangle(frame, (cell_x, cell_y), 
                            (cell_x + cell_size - 2, cell_y + cell_size - 2), 
                            border_color, border_thickness)
                
                # ラベル
                text_color = (0, 0, 0) if color_label in ['W', 'Y', 'O'] else (255, 255, 255)
                cv2.putText(frame, color_label, 
                           (cell_x + cell_size // 2 - 6, cell_y + cell_size // 2 + 6), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, text_color, 1)
        
        # 面のラベル
        label_x = start_x + (face_x + 1) * cell_size + cell_size // 4 - 4
        label_y = start_y + (face_y + 2) * cell_size + 15
        cv2.putText(frame, face_name, (label_x, label_y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
    
    return start_x, start_y, cell_size, face_positions

# --- マウスクリック処理 ---
def mouse_callback(event, x, y, flags, param):
    """マウスクリックで色を編集"""
    global selected_face, selected_cell, current_palette_index, collected_faces_global
    
    if event != cv2.EVENT_LBUTTONDOWN:
        return
    
    frame_shape, start_x, start_y, cell_size, face_positions, palette_x, palette_y, palette_cell_size = param
    
    # パレットクリック判定（色選択のみ）
    for i in range(len(color_palette)):
        px = palette_x + i * (palette_cell_size + 10)
        if px <= x <= px + palette_cell_size and palette_y <= y <= palette_y + palette_cell_size:
            current_palette_index = i
            # 色選択のみ（セルには塗らない）
            return
    
    # 展開図クリック判定（色を塗る）
    for face_name, (face_x, face_y) in face_positions.items():
        for i in range(3):
            for j in range(3):
                cell_x = start_x + (face_x + j) * cell_size
                cell_y = start_y + (face_y + i) * cell_size
                if cell_x <= x <= cell_x + cell_size and cell_y <= y <= cell_y + cell_size:
                    # クリックしたセルに現在選択中の色を塗る
                    face_str = collected_faces_global[face_name]
                    face_list = list(face_str)
                    face_list[i * 3 + j] = color_palette[current_palette_index]
                    collected_faces_global[face_name] = ''.join(face_list)
                    # 選択状態は使わない
                    return

# --- 編集モード画面 ---
def show_edit_mode(frame, collected_faces):
    """色編集モード画面"""
    # 編集可能な展開図
    start_x, start_y, cell_size, face_positions = draw_editable_cube_net(frame, collected_faces)
    
    # パレット
    palette_x, palette_y, palette_cell_size = draw_color_palette(frame)
    
    # 色のカウント情報を表示
    h, w = frame.shape[:2]
    info_y = start_y + 9 * cell_size + 40
    
    # 現在の色カウント
    cube_string_colors = "".join([collected_faces.get(f, "N"*9) for f in CAPTURE_ORDER_KOCIEMBA])
    color_counts = {}
    for color in cube_string_colors:
        color_counts[color] = color_counts.get(color, 0) + 1
    
    # 色カウント表示
    cv2.putText(frame, "Color Count (should be 9 each):", 
               (start_x, info_y), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
    
    color_names = {'W': 'White', 'R': 'Red', 'G': 'Green', 'B': 'Blue', 'O': 'Orange', 'Y': 'Yellow'}
    x_offset = start_x
    for i, (color, name) in enumerate(color_names.items()):
        count = color_counts.get(color, 0)
        text_color = (0, 255, 0) if count == 9 else (0, 0, 255)  # 緑=OK, 赤=NG
        
        text = f"{color}:{count}"
        cv2.putText(frame, text, 
                   (x_offset, info_y + 25), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, text_color, 2)
        x_offset += 80
    
    # 選択中のセル情報
    if selected_face is not None and selected_cell is not None:
        selection_text = f"Selected: {selected_face} Cell {selected_cell + 1}"
        cv2.putText(frame, selection_text, 
                   (start_x, info_y + 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    
    # 操作説明（下部）
    help_y = h - 25
    help_text = "ENTER: solve | R: restart"
    cv2.putText(frame, help_text, 
               (w // 2 - 150, help_y), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    return start_x, start_y, cell_size, face_positions, palette_x, palette_y, palette_cell_size

def get_camera_devices():
    """WindowsのDirectShowからカメラ名とOpenCV用インデックスを取得"""
    if FilterGraph is None:
        raise RuntimeError(
            "pygrabber がインストールされていません。\n"
            "PowerShellで次を実行してください:\n\n"
            "pip install pygrabber"
        )

    graph = FilterGraph()
    names = graph.get_input_devices()
    devices = []

    for index, name in enumerate(names):
        devices.append({"name": name, "index": index})

    return devices


def open_camera(index):
    """指定したカメラを開く。WindowsではDirectShowを優先。"""
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)

    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(index)

    if cap.isOpened():
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    return cap


def select_camera_gui():
    """カメラ名を表示し、プレビューを見ながらGUIで選択する。"""
    try:
        devices = get_camera_devices()
    except Exception as e:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("カメラ取得エラー", str(e))
        root.destroy()
        return None

    if not devices:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "カメラエラー",
            "使用可能なカメラが見つかりません。\n\n"
            "カメラを接続してからもう一度起動してください。"
        )
        root.destroy()
        return None

    if ImageTk is None:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "ライブラリエラー",
            "PillowのImageTkが利用できません。\n\n"
            "pip install pillow を実行してください。"
        )
        root.destroy()
        return None

    root = tk.Tk()
    root.title("Cube AR Solver - カメラ選択")
    root.geometry("900x700")
    root.resizable(False, False)

    # ---------- タイトル ----------
    tk.Label(
        root,
        text="Cube AR Solver",
        font=("Yu Gothic UI", 24, "bold")
    ).pack(pady=(18, 2))

    tk.Label(
        root,
        text="使用するカメラを選択してください",
        font=("Yu Gothic UI", 13)
    ).pack(pady=(0, 12))

    # ---------- プレビュー ----------
    preview_frame = tk.Frame(root, bg="black", width=640, height=360)
    preview_frame.pack(pady=5)
    preview_frame.pack_propagate(False)

    preview_label = tk.Label(
        preview_frame,
        text="カメラ映像を読み込んでいます...",
        fg="white",
        bg="black",
        font=("Yu Gothic UI", 13)
    )
    preview_label.pack(expand=True, fill="both")

    # ---------- カメラ選択 ----------
    select_frame = tk.Frame(root)
    select_frame.pack(fill="x", padx=120, pady=(15, 5))

    tk.Label(
        select_frame,
        text="カメラ",
        font=("Yu Gothic UI", 12, "bold")
    ).pack(side="left", padx=(0, 15))

    camera_var = tk.StringVar()
    combo = ttk.Combobox(
        select_frame,
        textvariable=camera_var,
        state="readonly",
        font=("Yu Gothic UI", 11),
        width=55
    )
    combo["values"] = [device["name"] for device in devices]
    combo.current(0)
    combo.pack(side="left", fill="x", expand=True)

    # 選択中のカメラ
    current_cap = [None]
    selected_index = [devices[0]["index"]]
    photo_ref = [None]

    def release_preview_camera():
        if current_cap[0] is not None:
            current_cap[0].release()
            current_cap[0] = None

    def start_preview(index):
        release_preview_camera()

        cap = open_camera(index)
        if not cap.isOpened():
            preview_label.configure(
                image="",
                text="このカメラを開けませんでした。"
            )
            return

        current_cap[0] = cap
        selected_index[0] = index
        update_preview()

    def update_preview():
        cap = current_cap[0]
        if cap is None:
            return

        ret, frame = cap.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(frame)
            image.thumbnail((640, 360), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image=image)
            photo_ref[0] = photo
            preview_label.configure(image=photo, text="")

        root.after(30, update_preview)

    def on_camera_changed(event=None):
        selected_name = camera_var.get()
        for device in devices:
            if device["name"] == selected_name:
                start_preview(device["index"])
                break

    combo.bind("<<ComboboxSelected>>", on_camera_changed)

    # ---------- 状態表示 ----------
    status_var = tk.StringVar(value=f"選択中: {devices[0]['name']}")
    tk.Label(
        root,
        textvariable=status_var,
        font=("Yu Gothic UI", 10),
        fg="#555555"
    ).pack(pady=3)

    # ---------- ボタン ----------
    button_frame = tk.Frame(root)
    button_frame.pack(pady=15)

    result = {"index": None}

    def confirm():
        if current_cap[0] is None or not current_cap[0].isOpened():
            messagebox.showwarning(
                "カメラエラー",
                "選択したカメラを開けません。\n別のカメラを選択してください。",
                parent=root
            )
            return

        result["index"] = selected_index[0]
        release_preview_camera()
        root.destroy()

    def cancel():
        result["index"] = None
        release_preview_camera()
        root.destroy()

    def update_status(event=None):
        status_var.set(f"選択中: {camera_var.get()}")

    combo.bind("<<ComboboxSelected>>", lambda event: (on_camera_changed(event), update_status(event)))

    tk.Button(
        button_frame,
        text="決定",
        command=confirm,
        font=("Yu Gothic UI", 12, "bold"),
        width=12,
        height=2
    ).pack(side="left", padx=10)

    tk.Button(
        button_frame,
        text="キャンセル",
        command=cancel,
        font=("Yu Gothic UI", 12),
        width=12,
        height=2
    ).pack(side="left", padx=10)

    root.protocol("WM_DELETE_WINDOW", cancel)

    # 最初のカメラをプレビュー
    start_preview(devices[0]["index"])

    root.mainloop()

    return result["index"]


def main():
    global edit_mode, selected_face, selected_cell, current_palette_index, collected_faces_global
    
    # 起動時にGUIでカメラを選択
    camera_index = select_camera_gui()
    if camera_index is None:
        return

    cap = open_camera(camera_index)
    if not cap.isOpened():
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "カメラエラー",
            "選択したカメラを開けませんでした。"
        )
        root.destroy()
        return
    
    collected_faces={}
    collected_faces_global = {}  # グローバル変数用
    current_index=0
    solving=False
    cube_already_solved=False
    solution_steps=[]
    step_index=0
    edit_mode=False
    guide_text={
        "U":"Place WHITE face UP",
        "F":"Place GREEN face FRONT",
        "R":"Place RED face FRONT",
        "B":"Place BLUE face FRONT",
        "L":"Place ORANGE face FRONT",
        "D":"Place YELLOW face DOWN",
    }
    
    # マウスコールバック設定用の変数
    mouse_params = None

    while True:
        ret,frame=cap.read()
        if not ret: break
        h,w,_=frame.shape
        cx,cy=w//2,h//2

        if edit_mode:
            # 編集モード
            collected_faces_global = collected_faces
            start_x, start_y, cell_size, face_positions, palette_x, palette_y, palette_cell_size = show_edit_mode(frame, collected_faces)
            
            # マウスコールバック設定
            if mouse_params is None:
                mouse_params = (frame.shape, start_x, start_y, cell_size, face_positions, palette_x, palette_y, palette_cell_size)
                cv2.setMouseCallback("Cube AR Solver", mouse_callback, mouse_params)
            
        elif cube_already_solved:
            # 揃っている表示
            draw_solved_message(frame)
            # 展開図も表示
            draw_large_cube_net(frame, collected_faces)
            
        elif not solving:
            current_face=CAPTURE_ORDER_CAPTURED[current_index]
            labels=sample_grid_labels(frame,cx,cy,GRID_STEP,current_face)
            # UI表示
            draw_capture_ui(frame, current_face, current_index + 1, guide_text)
            # draw_transparent_arrow(frame,current_face,cx,cy)  # ← 矢印描画を削除
            # 向き指定ガイド（左側）
            draw_orientation_guide(frame, current_face, cx, cy)
            # 展開図表示（右上に小さく）
            draw_cube_net(frame, collected_faces, current_face)
            
        else:
            show_steps(frame,solution_steps,step_index)
            # 展開図表示（左側に大きく）は消す

        cv2.imshow("Cube AR Solver",frame)
        key=cv2.waitKey(1) & 0xFF

        if key==13:  # Enter
            if edit_mode:
                # 編集モード終了 → 検証して解法へ
                edit_mode=False
                mouse_params=None
                cv2.setMouseCallback("Cube AR Solver", lambda *args: None)  # コールバック解除
                
                # Cube String作成（色文字列）
                cube_string_colors="".join([collected_faces[f] for f in CAPTURE_ORDER_KOCIEMBA])
                print("\nCube String Colors (U,R,F,D,L,B):",cube_string_colors)
                
                # 色を面記号に変換
                color_to_face = {
                    'W': 'U',  # White -> Up
                    'R': 'R',  # Red -> Right
                    'G': 'F',  # Green -> Front
                    'Y': 'D',  # Yellow -> Down
                    'O': 'L',  # Orange -> Left
                    'B': 'B',  # Blue -> Back
                    'N': 'N'   # 不明色はNのまま
                }
                cube_string = "".join(color_to_face.get(c, 'N') for c in cube_string_colors)
                print("Cube String Faces (U,R,F,D,L,B):",cube_string)
                
                # キューブストリングの検証（色記号で判定）
                if not validate_cube_string(cube_string_colors):
                    print("エラー: キューブストリングが無効です。もう一度編集してください。")
                    edit_mode=True
                    continue
                
                # 揃っているかチェック
                if is_cube_solved(cube_string):
                    print("キューブはすでに揃っています！")
                    cube_already_solved=True
                else:
                    try:
                        solution=kociemba.solve(cube_string)
                        solution_steps=solution.split()
                        print("Solution steps:",solution_steps)
                        solving=True
                        step_index=0
                    except Exception as e:
                        print("Error:",e)
                        print("エラーが発生しました。もう一度編集してください。")
                        edit_mode=True
                        continue
                
            elif cube_already_solved:
                # 揃っている状態からリスタート
                cube_already_solved=False
                
            elif not solving:
                face_str="".join(labels)
                # 不明色 'U' を 'N' に置き換え
                face_str = face_str.replace('U', 'N')
                collected_faces[current_face]=face_str
                print(f"{current_face} 面: {face_str}")
                current_index+=1
            
                if current_index==len(CAPTURE_ORDER_CAPTURED):
                    # D面180°回転補正
                    if 'D' in collected_faces:
                        collected_faces['D'] = rotate_face_180(collected_faces['D'])
                        print("D面を180°回転補正しました:", collected_faces['D'])
                    # 6面スキャン完了 → 自動的に編集モードへ
                    print("\n6面のスキャンが完了しました。編集モードに入ります。")
                    print("現在の各面の状態:")
                    for face in CAPTURE_ORDER_CAPTURED:
                        print(f"  {face}: {collected_faces[face]}")
                    edit_mode=True
                    current_index=0
                    
            else:
                step_index+=1
                if step_index>=len(solution_steps):
                    solving=False
                    solution_steps=[]
                    step_index=0
        
        elif key==ord("e"):  # 編集モード切り替え
            if edit_mode:
                edit_mode=False
                mouse_params=None
                cv2.setMouseCallback("Cube AR Solver", lambda *args: None)
            elif len(collected_faces)==6:  # 6面揃っている場合のみ
                edit_mode=True

        elif key==ord("r"):  # リスタート
            solving=False
            cube_already_solved=False
            edit_mode=False
            solution_steps=[]
            step_index=0
            collected_faces={}
            current_index=0
            mouse_params=None
            cv2.setMouseCallback("Cube AR Solver", lambda *args: None)
            print("Restarting...")

        elif key==ord("q"): break

    cap.release()
    cv2.destroyAllWindows()

if __name__=="__main__":
    main()