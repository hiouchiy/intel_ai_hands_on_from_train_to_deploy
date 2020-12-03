# インテル® AI - 学習からモデルデプロイまでの一連処理
OpenVINOを使って白黒画像を自動で色付けするアプリをさくっと作ってみます。
 
## Getting Started / スタートガイド
### Prerequisites / 必要条件
- Intel CPU（Core or Xeon）を搭載したマシン
    - Core: 第6世代以上
    - Xeon: Sandy Bridge以上
- OS: Linux（Ubuntu 18.04がお薦め）／Windows 10／
macOS 10.15
- Docker（※以下にインストール手順記載）
### Installing / インストール
#### ホストOSのポート開放（リモートアクセスする場合のみ）
このハンズオンではJupyter LabおよびOpenVINO Model Serverを使用します。特にサーバーにリモートアクセスしながら実施する場合は各環境ごとの手順に則り、ホストOSのポート「8888」、「9000」番を開放ください。
#### Dockerインストール
##### Linux（Ubuntu 18.04）
```Bash
sudo apt update
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu bionic stable"
sudo apt update
apt-cache policy docker-ce
sudo apt install -y docker-ce
sudo usermod -aG docker ${USER}
su - ${USER}
id -nG
```
##### Windows 10
https://docs.docker.jp/docker-for-windows/install.html
##### macOS
https://docs.docker.jp/docker-for-mac/install.html
#### Dockerイメージのダウンロード
今回はDocker版のOpenVINOを使用します（2020年12月3日現在、バージョン2021R1がダウンロードされる）。OSに直接インストールされたい方は[公式ドキュメント（英語）](https://docs.openvinotoolkit.org/latest/install_directly.html)を参照ください。
```Bash
docker pull openvino/ubuntu18_dev
```
#### Dockerコンテナの起動
コンテナはRootで起動します。また、8888番ポートをホストOSとコンテナとでバインドしておきます。かつ、ホストのディレクトリ（~/workspace）とコンテナのディレクトリ（/workspace）をバインドすることも忘れずに。作成したモデルファイルの受け渡しに使います。
```Bash
cd ~
mkdir workspace
docker run -it -u 0 --privileged -v ~/workspace:/workspace -p 8888:8888 openvino/ubuntu18_dev:latest /bin/bash
```
以降はコンテナ上での作業になります。
#### 追加モジュールのインストール
```Bash
apt-get update
apt-get install -y wget unzip git sudo
apt-get install -y ubuntu-restricted-extras　
(※↑でEULAにacceptを求められるのでyesと入力)
apt-get install -y ffmpeg
pip install jupyterlab munkres
pip uninstall tensorflow
pip install intel-tensorflow
```
#### 本レポジトリをClone
```Bash
cd ~
git clone https://github.com/hiouchiy/intel_ai_hands_on_from_train_to_deploy.git
```
#### Jupyter Labの起動
```Bash
KMP_AFFINITY=granularity=fine,compact,1,0 KMP_BLOCKTIME=1 KMP_SETTINGS=1 OMP_NUM_THREADS=物理コア数 jupyter lab --ip=0.0.0.0 --no-browser --allow-root
```
#### WebブラウザからJupyter Labにアクセス
前のコマンド実行すると以下のようなログが出力されまして、最後にローカルホスト（127.0.0.1）のトークン付きURLが表示されるはずです。こちらをWebブラウザにペーストしてアクセスください。リモートアクセスされている場合はIPアドレスをサーバーのホストOSのIPアドレスに変更してください。
```
root@f79f54d47c1b:~# jupyter lab --allow-root --ip=0.0.0.0 --no-browser
[I 09:13:08.932 LabApp] JupyterLab extension loaded from /usr/local/lib/python3.6/dist-packages/jupyterlab
[I 09:13:08.933 LabApp] JupyterLab application directory is /usr/local/share/jupyter/lab
[I 09:13:08.935 LabApp] Serving notebooks from local directory: /root
[I 09:13:08.935 LabApp] Jupyter Notebook 6.1.4 is running at:
[I 09:13:08.935 LabApp] http://f79f54d47c1b:8888/?token=2d6863a5b833a3dcb1a57e3252e641311ea7bc8e65ad9ca3
[I 09:13:08.935 LabApp]  or http://127.0.0.1:8888/?token=2d6863a5b833a3dcb1a57e3252e641311ea7bc8e65ad9ca3
[I 09:13:08.935 LabApp] Use Control-C to stop this server and shut down all kernels (twice to skip confirmation).
[C 09:13:08.941 LabApp] 
    
    To access the notebook, open this file in a browser:
        file:///root/.local/share/jupyter/runtime/nbserver-33-open.html
    Or copy and paste one of these URLs:
        http://f79f54d47c1b:8888/?token=2d6863a5b833a3dcb1a57e3252e641311ea7bc8e65ad9ca3
     or http://127.0.0.1:8888/?token=2d6863a5b833a3dcb1a57e3252e641311ea7bc8e65ad9ca3
```
↑こちらの例の場合は、最後の "http://127.0.0.1:8888/?token=2d6863a5b833a3dcb1a57e3252e641311ea7bc8e65ad9ca3" です。
#### Notebookの起動
Jupyter Lab上で「intel_ai_hands_on_from_train_to_deploy」フォルダーに入り、その中の「how_to_optimize_custom_model_with_openvino.ipynb」を開き、後はノートブックの内容に従って進めてください。

---
## 応用編：OpenVINO Model Serverを使ってモデルをWeb API化
[OpenVINO Model Server](https://github.com/openvinotoolkit/model_server)を使うとOpenVINOのモデルを簡単にWeb API化できます。以下の手順通りにダウンロードおよび起動をしてください。
### Installing / インストール
#### OpenVINO Model ServerのDockerイメージをダウンロード
ホストOS上でもう一つターミナルを開き、下記コマンドを実行
```Bash
docker pull openvino/model_server:latest
```
#### OpenVINOの事前学習済みモデルをダウンロード
ハンズオンの中で使用した日本語の手書き文字認識用の事前学習済みモデルをダウンロードして、ホストOS上の適当なフォルダに格納しておく
#### OpenVINO Model Serverを起動
各パラメータの意味については[こちら](https://github.com/openvinotoolkit/model_server/blob/main/docs/docker_container.md)を参照ください。
```Bash
docker run -d -v ~/workspace/optimized:/models/dogcat/1 -p 9000:9000 openvino/model_server:latest --model_path /models/dogcat --model_name dogcat --port 9000 --log_level DEBUG --shape auto
```
またはモデルファイルをクラウドストレージ（Azure／AWS／GCP）から読み込むことも可能です。Azure Blob Storageの場合は以下の通りです。事前に接続文字列を取得し、それをホストOSの環境変数としてセットください。かつモデルフォルダの下はバージョンごと（1から開始）にサブフォルダを作成し、そちらにモデルファイル一式を格納しておく必要があります。
```Bash
docker run --rm -d -p 9000:9000 -e AZURE_STORAGE_CONNECTION_STRING="%AZURE_STORAGE_CONNECTION_STRING%" openvino/model_server:latest --model_path az://コンテナ名/モデルフォルダ名 --model_name dogcat --port 9000
```
具体的には以下の通り。
```Bash
docker run --rm -d -p 9000:9000 -e AZURE_STORAGE_CONNECTION_STRING="%AZURE_STORAGE_CONNECTION_STRING%" openvino/model_server:latest --model_path az://ovms/dogcat --model_name dogcat --port 9000
```
#### NotebookからOpenVINO Model Serverへアクセス
前のコンテナ（Jupyter Lab実行中）のNotebook（how_to_optimize_custom_model_with_openvino.ipynb）に戻り、「【応用編】OpenVINO Model Serverを使う」から再開ください。
## License / ライセンス
このプロジェクトは Apache 2.0の元にライセンスされています。