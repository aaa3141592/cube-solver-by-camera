# Cube Solver by Camera

カメラでルービックキューブの各面をスキャンし、キューブの状態を自動認識して、解法を計算・表示するアプリです。

## Features

* カメラを使用したルービックキューブの状態スキャン
* 各マスの色を画像から自動認識
* 6面すべての状態を取得
* 認識した状態から解法を計算
* キューブの状態や解法手順を画面に表示
* 認識結果を手動で編集可能
* 複数のカメラから使用するカメラをGUIで選択可能
* スキャンのやり直しに対応

## Demo

カメラにルービックキューブを映し、画面上のガイドに合わせて各面を順番にスキャンします。

6面のスキャンが完了すると、現在のキューブ状態から解法を計算し、キューブをそろえるための手順を表示します。

## How It Works

基本的な処理の流れは以下の通りです。

```text
Camera
  ↓
Cube Detection
  ↓
Color Recognition
  ↓
6 Faces Scan
  ↓
Cube State Validation
  ↓
Kociemba Solver
  ↓
Solution Display
```

1. カメラを選択
2. ルービックキューブの面をカメラに映す
3. 各マスの色を認識
4. 6面分の状態を取得
5. キューブの状態を検証
6. Kociembaアルゴリズムを使用して解法を計算
7. 必要な手順を画面に表示

## Requirements

* Windows
* Python 3.x
* Webカメラ
* ルービックキューブ

### Python Packages

```bash
pip install opencv-python
pip install numpy
pip install kociemba
pip install pillow
pip install pygrabber
```

## Installation

リポジトリをクローンします。

```bash
git clone https://github.com/aaa3141592/cube-solver-by-camera.git
cd cube-solver-by-camera
```

必要なライブラリをインストールします。

```bash
pip install -r requirements.txt
```

アプリを起動します。

```bash
python cube_solver_by_camera_gui.py
```

## Camera Selection

起動するとカメラ選択画面が表示されます。

接続されているカメラを名前で選択し、プレビューを確認してから使用するカメラを決定できます。

複数のWebカメラやキャプチャデバイスを接続している環境でも、カメラ番号を直接入力する必要はありません。

## Controls

| Key     | Function      |
| ------- | ------------- |
| `Enter` | 決定 / 次のステップ   |
| `E`     | 編集モード切り替え     |
| `R`     | スキャンを最初からやり直す |
| `Q`     | アプリを終了        |

## Manual Editing

カメラによる色認識が正しく行われなかった場合は、編集モードを使用して認識結果を手動で修正できます。

これにより、照明やカメラの性能などによって一部の色認識に失敗した場合でも、状態を修正して解法を計算できます。

## Solver

キューブの解法計算には **Kociemba algorithm** を使用しています。

入力されたキューブ状態をKociemba形式へ変換し、解法手順を生成します。

## Project Structure

```text
cube-solver-by-camera/
├── cube_solver_by_camera_gui.py
├── msgothic.ttc
├── requirements.txt
└── README.md
```

## Future Improvements

* [ ] 色認識精度の向上
* [ ] 自動でのキューブ位置検出
* [ ] スキャン時の認識結果フィードバック改善
* [ ] 解法手順のアニメーション表示
* [ ] 3Dキューブによる解法表示
* [ ] カメラ映像上へのAR形式の手順表示
* [ ] スキャン・解法処理のさらなる自動化

## License

This project is currently for personal and educational use.
