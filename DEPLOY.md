# 실습 가이드 — 받아서, 고치고, 올리고, 서버에서 실행하기

| 파트 | 내용 | 서버 포트 |
| --- | --- | --- |
| **1부** | 강사 저장소 받기 → 로컬 테스트·수정 → **내 GitHub** 에 올리기 → EC2에서 **파이썬으로** 실행 | `8501` |
| **2부** | 도커 기초 — 실무 DB(**PostgreSQL · MySQL**)를 받아서 **올렸다 내렸다** | 열지 않음 |

```
강사 GitHub ──clone──▶ 내 PC ──push──▶ 내 GitHub ──clone──▶ EC2
                      (테스트·수정)                        ├─ 1부: streamlit 직접 실행 (:8501)
                                                           └─ 2부: DB 컨테이너        (포트 안 엶)
```

---

# 1부. 파이썬으로 실행하기

## 1-1. 강사 저장소 받기 (내 PC)

```bash
git clone https://github.com/<강사계정>/<저장소>.git stock_app
cd stock_app
```

## 1-2. 로컬 환경 만들기

```bash
conda create -n stock_app python=3.13 -y
conda activate stock_app
pip install -r requirements.txt
```

## 1-3. `.env` 만들기

`.env` 는 비밀번호가 들어가는 파일이라 **저장소에 없습니다.** 견본을 복사해서 만듭니다.

```bash
copy .env.sample .env        # Windows
cp .env.sample .env          # macOS / Linux
```

### Gmail 앱 비밀번호가 있는 경우

1. Google 계정 → **보안** → **2단계 인증** 켜기
2. 보안 → **앱 비밀번호** → 이름 입력 후 생성 → 16자리 복사
3. `.env` 에 입력

```ini
GMAIL_USER=내계정@gmail.com
GMAIL_APP_PASSWORD=abcdefghijklmnop
```

### 메일 없이 테스트하는 경우

`GMAIL_USER`, `GMAIL_APP_PASSWORD` 를 **빈 값**으로 두고 `DEV_SHOW_LINK=true` 로 두세요.
회원가입 시 인증 링크가 메일 대신 **화면에 표시**되어 그대로 눌러 가입할 수 있습니다.

```ini
GMAIL_USER=
GMAIL_APP_PASSWORD=
DEV_SHOW_LINK=true
```

## 1-4. 로컬 실행

```bash
streamlit run app.py
```

`http://localhost:8501` → 회원가입 → 인증 → 로그인 → 관심 종목 추가 → 차트 확인.

## 1-5. 수정하기

필요한 부분을 고치고 다시 실행해 확인합니다. Streamlit 은 파일을 저장하면 화면 우상단에 **Rerun** 이 떠서 바로 반영됩니다.

## 1-6. 내 GitHub 에 올리기

### ① GitHub 에서 빈 저장소 만들기

GitHub → **New repository** → 이름 입력 → **README, .gitignore, License 를 모두 체크하지 않고** 생성
(체크하면 첫 push 에서 충돌이 납니다)

### ② 연결 대상을 내 저장소로 바꾸기

지금 `origin` 은 **강사 저장소**를 가리키고 있습니다. 강사 것은 `upstream` 으로 이름을 바꾸고, 내 저장소를 `origin` 으로 추가합니다.

```bash
git remote rename origin upstream
git remote add origin https://github.com/<내계정>/<내저장소>.git
git remote -v
```

```
origin    https://github.com/<내계정>/<내저장소>.git (push)     ← 내 것
upstream  https://github.com/<강사계정>/<저장소>.git (fetch)    ← 강사 것
```

### ③ 커밋하고 올리기

```bash
git add .
git status                  # ★ .env 와 stock_app.db 가 목록에 없는지 반드시 확인
git commit -m "로컬 테스트 후 수정"
git push -u origin main
```

> **`.env` 가 목록에 보이면 절대 커밋하지 마세요.** Gmail 앱 비밀번호가 인터넷에 공개됩니다.
> 실수로 올렸다면 **앱 비밀번호를 즉시 삭제하고 새로 발급**하세요. 커밋을 지워도 기록이 남습니다.

### 강사 저장소가 업데이트되면

```bash
git pull upstream main      # 강사 변경사항 받기
git push origin main        # 내 저장소에도 반영
```

## 1-7. EC2 준비

### 인스턴스

- **Ubuntu 24.04**, `t3.small` 이상 권장
- 키 페어(.pem) 다운로드

### 보안 그룹 — 인바운드 규칙

| 유형 | 포트 | 소스 | 용도 |
| --- | --- | --- | --- |
| SSH | 22 | 내 IP | 접속 |
| 사용자 지정 TCP | **8501** | 0.0.0.0/0 | 1부 앱 |

> Gmail 메일 발송(465 포트)은 **아웃바운드**라 따로 열 필요가 없습니다. AWS가 막는 건 25번뿐입니다.
>
> 2부의 DB는 **포트를 열지 않습니다.** DB 포트(5432, 3306)를 `0.0.0.0/0` 에 열면
> 몇 시간 안에 자동 스캐너가 비밀번호 대입 공격을 시작합니다.

### 접속

```bash
ssh -i 내키.pem ubuntu@<EC2퍼블릭IP>
```

## 1-8. EC2에서 실행

### ① 기본 도구 설치

```bash
sudo apt update
sudo apt install -y git python3-venv python3-pip
python3 --version            # 3.12.x (Ubuntu 24.04 기본)
```

서버에서는 conda 대신 가벼운 **venv** 를 씁니다.

### ② 내 저장소 받기

```bash
git clone https://github.com/<내계정>/<내저장소>.git stock_app
cd stock_app
```

### ③ 가상환경 + 패키지

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> 메모리가 1GB인 `t2.micro` 에서 설치 도중 `Killed` 가 뜨면 스왑을 먼저 만드세요.
> ```bash
> sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
> sudo mkswap /swapfile && sudo swapon /swapfile
> ```

### ④ 서버용 `.env`

```bash
cp .env.sample .env
nano .env
```

**`APP_BASE_URL` 을 반드시 EC2 주소로 바꿉니다.** 안 바꾸면 인증 메일의 링크가 `localhost` 를 가리켜서 **아무도 가입을 완료할 수 없습니다.**

```ini
APP_BASE_URL=http://<EC2퍼블릭IP>:8501
```

저장: `Ctrl+O` → `Enter` → `Ctrl+X`

### ⑤ 실행

먼저 화면에 띄워서 오류가 없는지 확인합니다.

```bash
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

브라우저에서 `http://<EC2퍼블릭IP>:8501` 접속 확인 → `Ctrl+C` 로 종료.

> `--server.address 0.0.0.0` 이 없으면 서버 안에서만 열려서 외부 접속이 안 됩니다.

### ⑥ 터미널을 닫아도 계속 돌게 하기

```bash
nohup streamlit run app.py --server.port 8501 --server.address 0.0.0.0 \
      --server.headless true > app.log 2>&1 &
```

| 명령 | 용도 |
| --- | --- |
| `tail -f app.log` | 로그 보기 (`Ctrl+C` 로 빠져나옴) |
| `ps aux \| grep streamlit` | 실행 중인지 확인 |
| `pkill -f "streamlit run"` | 종료 |

## 1-9. 코드를 고친 뒤 서버에 반영

```bash
# 내 PC
git add . && git commit -m "수정 내용" && git push

# EC2
cd ~/stock_app
git pull
pkill -f "streamlit run"
source .venv/bin/activate
nohup streamlit run app.py --server.port 8501 --server.address 0.0.0.0 \
      --server.headless true > app.log 2>&1 &
```

`requirements.txt` 가 바뀌었다면 `pip install -r requirements.txt` 를 한 번 더 실행합니다.

---

# 2부. 도커 기초 — DB를 올렸다 내렸다

실무에서 도커를 가장 많이 쓰는 곳은 **"개발용 DB를 몇 초 만에 띄우고 지우기"** 입니다.
DB를 직접 설치하지 않고, 이미 만들어진 이미지로 **PostgreSQL** 과 **MySQL** 을 올렸다 내리면서 도커의 기본을 익힙니다.

```
받기(pull) → 올리기(run) → 들어가서 데이터 넣기(exec) → 내리기(stop) → 지우기(rm) → 다시 올리기
                                                              └─ 데이터는 남아 있을까?
```

## 먼저 용어 세 개

| 용어 | 비유 | 설명 |
| --- | --- | --- |
| **이미지** | 설치 파일 | 프로그램과 실행에 필요한 것을 묶은 것. 읽기 전용 |
| **컨테이너** | 설치해서 켠 프로그램 | 이미지를 실행한 것. 지우면 안에 있던 것도 같이 사라짐 |
| **볼륨** | 외장 하드 | 컨테이너 밖의 저장 공간. 컨테이너를 지워도 남음 |

## 2-1. EC2에 도커 설치

```bash
sudo apt update
sudo apt install -y docker.io
sudo usermod -aG docker $USER
exit
```

**다시 접속해야** 그룹 설정이 적용됩니다. 재접속 후:

```bash
docker --version
docker run hello-world
```

`Hello from Docker!` 가 나오면 성공입니다.

---

## 2-2. PostgreSQL 올리기

### ① 이미지 받기

```bash
docker pull postgres:18
docker images
```

> 태그(`:18`)를 꼭 붙이세요. 붙이지 않으면 `latest` 를 받는데, 나중에 버전이 바뀌면 같은 명령이 다르게 동작할 수 있습니다.

### ② 볼륨 만들기

```bash
docker volume create pgdata
docker volume ls
```

### ③ 컨테이너 올리기

```bash
docker run -d --name pg-db \
  -e POSTGRES_PASSWORD=1234 \
  -v pgdata:/var/lib/postgresql \
  postgres:18
```

| 옵션 | 의미 |
| --- | --- |
| `-d` | 백그라운드 실행 |
| `--name pg-db` | 컨테이너 이름. 이후 명령에서 이 이름을 씀 |
| `-e POSTGRES_PASSWORD=1234` | **환경변수**로 관리자 비밀번호 지정. 1부의 `.env` 와 같은 개념. **없으면 컨테이너가 바로 꺼짐** |
| `-v pgdata:/var/lib/postgresql` | 볼륨을 DB 저장 위치에 연결 |
| `postgres:18` | 실행할 이미지 |

> ⚠️ **PostgreSQL 18부터 저장 경로가 바뀌었습니다.** 인터넷 자료 대부분은 예전 경로인
> `/var/lib/postgresql/data` 를 씁니다. 18에서는 **`/var/lib/postgresql`** 로 연결해야 합니다.

> `-p` 옵션이 없는 점에 주목하세요. 컨테이너 **안으로 들어가서** 접속하므로 포트를 열 필요가 없습니다.

### ④ 준비될 때까지 기다리기

```bash
docker ps
docker logs pg-db
```

로그 끝에 `database system is ready to accept connections` 가 보이면 준비 완료입니다. 처음에는 몇 초 걸립니다.

### ⑤ 들어가서 데이터 넣기

```bash
docker exec -it pg-db psql -U postgres
```

프롬프트가 `postgres=#` 로 바뀝니다.

```sql
CREATE TABLE watchlist (symbol TEXT, name TEXT);
INSERT INTO watchlist VALUES ('005930', '삼성전자'), ('TSLA', 'Tesla');
SELECT * FROM watchlist;
```

```
 symbol |   name
--------+----------
 005930 | 삼성전자
 TSLA   | Tesla
(2 rows)
```

나가기: `\q`

### ⑥ 올렸다 내렸다 실험 ★

| 실험 | 결과 |
| --- | --- |
| **A.** 중지 → 시작 | 데이터 **남아 있음** |
| **B.** 삭제 → **같은 볼륨으로** 다시 올리기 | 데이터 **남아 있음** |
| **C.** 삭제 → **볼륨 없이** 다시 올리기 | 데이터 **사라짐** |

매 실험 후 이 명령으로 확인합니다.

```bash
docker exec -it pg-db psql -U postgres -c "SELECT * FROM watchlist;"
```

**실험 A — 중지했다 다시 시작**

```bash
docker stop pg-db
docker ps -a                     # STATUS 가 Exited
docker start pg-db
```

**실험 B — 컨테이너를 지워도 볼륨이 데이터를 지킨다**

```bash
docker rm -f pg-db
docker volume ls                 # pgdata 는 남아 있음
docker run -d --name pg-db -e POSTGRES_PASSWORD=1234 -v pgdata:/var/lib/postgresql postgres:18
```

몇 초 뒤 확인 → 삼성전자, Tesla 가 그대로 나옵니다.

**실험 C — 볼륨 없이 올리면**

```bash
docker rm -f pg-db
docker run -d --name pg-db -e POSTGRES_PASSWORD=1234 postgres:18
```

몇 초 뒤 확인 →

```
ERROR:  relation "watchlist" does not exist
```

새 컨테이너는 **빈 DB로 시작**합니다. 실무에서 "서버를 재배포했더니 데이터가 전부 날아갔다" 는 사고가 정확히 이것입니다.

실험이 끝나면 원래대로 되돌려 둡니다.

```bash
docker rm -f pg-db
docker run -d --name pg-db -e POSTGRES_PASSWORD=1234 -v pgdata:/var/lib/postgresql postgres:18
```

---

## 2-3. MySQL 올리기

같은 흐름을 MySQL로 반복합니다. **옵션 이름과 경로만 다르고 구조는 똑같다**는 것을 확인하는 게 목표입니다.

### ⓪ PostgreSQL 먼저 내리기

MySQL은 메모리를 400MB 이상 씁니다. 작은 인스턴스에서는 둘을 동시에 띄우면 컨테이너가 죽을 수 있습니다.

```bash
docker stop pg-db
```

### ① 받기 · 볼륨 · 올리기

```bash
docker pull mysql:8.4
docker volume create mysqldata

docker run -d --name mysql-db \
  -e MYSQL_ROOT_PASSWORD=1234 \
  -e MYSQL_DATABASE=stock \
  -v mysqldata:/var/lib/mysql \
  mysql:8.4
```

| MySQL 옵션 | PostgreSQL 에서는 |
| --- | --- |
| `-e MYSQL_ROOT_PASSWORD=1234` | `-e POSTGRES_PASSWORD=1234` |
| `-e MYSQL_DATABASE=stock` | 처음 뜰 때 `stock` DB를 만들어 줌 (PostgreSQL 은 기본 DB `postgres` 를 그대로 씀) |
| `-v mysqldata:/var/lib/mysql` | `-v pgdata:/var/lib/postgresql` |

### ② 준비될 때까지 기다리기

MySQL은 PostgreSQL보다 초기화가 **오래 걸립니다** (10~30초).

```bash
docker logs -f mysql-db
```

`ready for connections` 가 **`port: 3306`** 과 함께 찍히면 준비 완료입니다. `Ctrl+C` 로 빠져나옵니다.

> 초기화 도중에는 `port: 0` 이 붙은 `ready for connections` 가 먼저 한 번 나옵니다. 이건 임시 서버라 아직 접속하면 안 됩니다.
> 너무 일찍 접속하면 `Can't connect to local MySQL server through socket` 오류가 납니다.

### ③ 들어가서 데이터 넣기

```bash
docker exec -it -e LANG=C.UTF-8 mysql-db mysql -u root -p stock
```

`Enter password:` 에 `1234` 입력 (화면에 표시되지 않음).

> `-e LANG=C.UTF-8` 은 **한글 입력용**입니다. MySQL 이미지는 기본 언어 설정이 없어서, 이 옵션을 빼면 한글이 입력되지 않거나 깨질 수 있습니다.

```sql
CREATE TABLE watchlist (symbol VARCHAR(20), name VARCHAR(50));
INSERT INTO watchlist VALUES ('005930', '삼성전자'), ('TSLA', 'Tesla');
SELECT * FROM watchlist;
```

```
+--------+--------------+
| symbol | name         |
+--------+--------------+
| 005930 | 삼성전자     |
| TSLA   | Tesla        |
+--------+--------------+
```

나가기: `exit`

> PostgreSQL 은 `TEXT` 만으로 충분했지만, MySQL 은 보통 `VARCHAR(길이)` 를 씁니다.

### ④ 올렸다 내렸다 실험

PostgreSQL 과 **같은 실험**을 이름만 바꿔 합니다. 확인 명령:

```bash
docker exec -it mysql-db mysql -u root -p1234 stock -e "SELECT * FROM watchlist;"
```

> `-p1234` 처럼 **붙여 쓰면** 비밀번호를 묻지 않습니다. (띄어 쓰면 `1234` 를 DB 이름으로 착각합니다)
> 실습용 편의일 뿐, 실무에서는 명령 기록에 비밀번호가 남으므로 쓰지 않습니다.

```bash
# A. 중지 → 시작
docker stop mysql-db
docker start mysql-db

# B. 삭제 → 같은 볼륨으로 다시
docker rm -f mysql-db
docker run -d --name mysql-db -e MYSQL_ROOT_PASSWORD=1234 -e MYSQL_DATABASE=stock -v mysqldata:/var/lib/mysql mysql:8.4

# C. 삭제 → 볼륨 없이 다시
docker rm -f mysql-db
docker run -d --name mysql-db -e MYSQL_ROOT_PASSWORD=1234 -e MYSQL_DATABASE=stock mysql:8.4
```

실험 B·C 는 **초기화를 기다린 뒤** 확인하세요. 실험 C 의 결과:

```
ERROR 1146 (42S02): Table 'stock.watchlist' doesn't exist
```

`stock` DB는 `-e MYSQL_DATABASE` 덕분에 새로 만들어졌지만, **그 안의 테이블과 데이터는 없습니다.**

---

## 2-4. 두 DB 비교

| | PostgreSQL | MySQL |
| --- | --- | --- |
| 이미지 | `postgres:18` | `mysql:8.4` |
| 필수 환경변수 | `POSTGRES_PASSWORD` | `MYSQL_ROOT_PASSWORD` |
| 볼륨 연결 경로 | `/var/lib/postgresql` | `/var/lib/mysql` |
| 접속 명령 | `psql -U postgres` | `mysql -u root -p` |
| 나가기 | `\q` | `exit` |
| 기본 포트 | 5432 | 3306 |
| 초기화 시간 | 몇 초 | 10~30초 |
| 메모리 | 가벼움 | 400MB 이상 |

**도커 명령(`pull / run / exec / stop / start / rm`)은 완전히 같습니다.** 달라지는 건 이미지 설명서에 적힌 **환경변수와 저장 경로**뿐입니다. 다른 서비스를 도커로 띄울 때도 [Docker Hub](https://hub.docker.com) 설명서에서 이 두 가지만 찾으면 됩니다.

## 2-5. 명령 요약

| 하는 일 | 명령 |
| --- | --- |
| 이미지 받기 | `docker pull postgres:18` |
| 이미지 목록 | `docker images` |
| 볼륨 만들기 / 목록 | `docker volume create 이름` / `docker volume ls` |
| 올리기 | `docker run -d --name 이름 -e 변수=값 -v 볼륨:경로 이미지` |
| 실행 중 목록 | `docker ps` (중지된 것까지: `docker ps -a`) |
| 로그 | `docker logs -f 이름` |
| 들어가기 | `docker exec -it 이름 명령` |
| 내리기 / 다시 올리기 | `docker stop 이름` / `docker start 이름` |
| 컨테이너 삭제 | `docker rm -f 이름` |
| 이미지 삭제 | `docker rmi 이미지` |
| 볼륨 삭제 | `docker volume rm 이름` |

## 2-6. 정리

```bash
docker rm -f pg-db mysql-db                 # 컨테이너 삭제
docker volume rm pgdata mysqldata           # ⚠ 데이터까지 삭제
docker volume prune                         # 실험 C 에서 생긴 이름 없는 볼륨 정리
docker rmi postgres:18 mysql:8.4 hello-world
```

> 실험 C 처럼 `-v` 없이 올린 DB도 사실은 **이름 없는 볼륨**을 자동으로 만듭니다.
> `docker volume ls` 에 긴 해시 이름으로 쌓여 있으니 `prune` 으로 정리하세요.

## 더 해보고 싶다면

- 1부의 관심종목 앱은 SQLite(파일)를 씁니다. 실제 서비스라면 방금 띄운 PostgreSQL·MySQL 같은 DB로 옮기게 됩니다.
- 이 저장소의 `Dockerfile` 로 **내 앱을 이미지로 만드는 것**(`docker build -t stock-app .`)이 다음 단계입니다.

---

# 자주 막히는 곳

| 증상 | 원인 / 해결 |
| --- | --- |
| 브라우저에서 접속이 안 됨 | 보안 그룹에 8501 포트 미개방 |
| 1부에서 접속이 안 됨 | `--server.address 0.0.0.0` 누락 |
| 가입 메일의 링크가 안 열림 | `.env` 의 `APP_BASE_URL` 이 localhost 또는 포트가 틀림 |
| 메일이 안 감 | 앱 비밀번호 오류. 화면의 "Gmail 인증 실패" 메시지 확인 |
| `git push` 가 거절됨 | 빈 저장소가 아님(README 체크함). `git pull origin main --allow-unrelated-histories` 후 다시 push |
| `.env` 가 `git status` 에 보임 | `.gitignore` 가 없거나 이름이 틀림. **커밋하지 말 것** |
| `pip install` 중 `Killed` | 메모리 부족 → 스왑 추가 (1-8 ③ 참고) |
| `docker: permission denied` | `usermod` 후 재접속을 안 함 |
| `docker run` 에서 이름 충돌 (`already in use`) | 같은 이름의 컨테이너가 남아 있음 → `docker rm -f pg-db` |
| DB 컨테이너가 바로 꺼짐 (`docker ps` 에 없음) | 비밀번호 환경변수(`-e`) 누락 → `docker logs 이름` 으로 확인 |
| `exec` 직후 접속 오류 | 아직 초기화 중 → `docker logs` 에서 준비 완료 메시지 확인 후 재시도 |
| PostgreSQL 볼륨을 붙였는데 데이터가 안 남음 | 18 버전에 옛 경로(`/var/lib/postgresql/data`) 사용 → `/var/lib/postgresql` |
| MySQL 에서 한글이 입력 안 됨 / 깨짐 | `docker exec` 에 `-e LANG=C.UTF-8` 추가 |
| MySQL 컨테이너가 죽음 (`Exited (137)`) | 메모리 부족 → PostgreSQL 먼저 내리기, 스왑 추가 (1-8 ③) |
| EC2 재시작 후 접속 주소가 바뀜 | 퍼블릭 IP 변경 → `APP_BASE_URL` 수정 (고정하려면 Elastic IP) |

---

# 알아둘 한계

- **HTTPS가 아닙니다.** 로그인 비밀번호가 암호화 없이 오갑니다. 실습용으로만 쓰세요.
- 로그인은 브라우저 세션 기반이라 **새로고침하면 로그아웃**됩니다.
- 실습이 끝나면 **EC2 인스턴스를 중지**하세요. 켜두면 요금이 나옵니다.
