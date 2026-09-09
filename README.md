# Rift Signal v1.4.1 한국어판

FastAPI 기반 League of Legends 개인 훈련 루틴 서비스의 완전한 한국어판입니다. 최근 경기와 같은 주 역할의 KR 최상위 티어 표본을 비교해 우선 과제를 찾고, 실행 가능한 7일 루틴을 만듭니다. 화면, 분석 결과, 오류 메시지를 한국어로 제공하며 아래 절차는 모두 VS Code 안에서 진행할 수 있습니다.

- GitHub: <https://github.com/hd-jung/riot-player-analysis-kor>
- Vercel: <https://riot-player-analysis-kor.vercel.app>

## 서비스가 만드는 것

Riot ID를 입력하면 최근 경기에서 승률, KDA, 분당 CS, 평균 데스를 계산합니다. 같은 주 역할의 KR 마스터·그랜드마스터·챌린저 표본과 비교한 뒤 격차가 큰 항목을 우선순위로 정해 다음 내용을 제공합니다.

- 개인별 핵심 개선 과제 최대 3개
- 매일 할 일과 측정 목표가 있는 7일 훈련 일정
- 추천 챔피언을 활용한 집중 랭크 세션
- 7일차 재측정 및 다음 주 조정 안내
- 브라우저에만 저장되는 일자별 완료 시각과 진행 상태
- 오늘의 훈련 자동 전환, 연속 수행일, 완료 후 성과 재측정
- 월간 활동 달력과 분석 체크포인트 히스토리
- KDA, 분당 CS, 평균 데스, 승률의 첫 분석 대비 성장 추이
- 실제 변화량을 바탕으로 생성되는 주간 코치 노트

기준 데이터는 프로 선수 경기 데이터가 아니며 코칭 결과를 보장하지 않습니다. 현재 포함된 정적 최상위 티어 표본을 방향성 기준으로 사용하고, 사용자 표본이 적을 때는 신뢰도를 `초기`, `보통`, `높음`으로 표시합니다.

## 검수용 데모 계정

```text
dummy_player#KR1
```

이 Riot ID는 실제 Riot 계정이나 API 키를 사용하지 않습니다. 입력하면 최근 한 달간의 분석 체크포인트 5개, 훈련 기록 20일 이상, 현재 진행 중인 7일 루틴과 점진적인 경기 지표 성장 추이가 브라우저에 자동 생성됩니다. 다른 Riot ID의 실제 기록과는 분리됩니다.

## 1. VS Code에서 프로젝트 열기

VS Code에서 `File > Open Folder`를 누르고 이 폴더를 엽니다.

```text
D:\workspace\4. hong\game_v1.2(korean)
```

`Ctrl+Shift+P`를 누른 뒤 `Python: Select Interpreter`에서 `game_py311` 환경을 선택합니다. 목록에 보이지 않으면 다음 인터프리터 경로를 직접 선택합니다.

```text
C:\Users\dossa\anaconda3\envs\game_py311\python.exe
```

이후 `Terminal > New Terminal`로 VS Code 통합 터미널을 엽니다.

## 2. 최초 설치

PowerShell 터미널에서 실행합니다.

```powershell
conda activate game_py311
python -m pip install -r requirements.txt
```

또는 `Ctrl+Shift+P > Tasks: Run Task > Rift Signal 한국어판: 의존성 설치`를 실행합니다.

## 3. 로컬 Riot API 키 등록

Riot Developer Portal에서 새로운 개발 키를 발급받습니다.

1. `.env.example`을 복사하여 `.env` 파일을 만듭니다.
2. `.env`를 열고 현재 키를 입력합니다.

```dotenv
RIOT_API_KEY=RGAPI-발급받은-키
```

PowerShell로 파일을 복사할 때:

```powershell
Copy-Item .env.example .env
```

`.env`는 `.gitignore`에 포함되어 GitHub에 올라가지 않습니다. 키를 README, 소스 코드, 커밋 메시지 또는 터미널 명령 자체에 직접 적지 마세요.

키를 바꾼 후 실행 중인 서버가 있다면 터미널에서 `Ctrl+C`로 종료하고 다시 실행해야 합니다.

## 4. 로컬 서버 실행

```powershell
python -m uvicorn main:app --reload
```

브라우저에서 다음 주소를 엽니다.

- 서비스: <http://127.0.0.1:8000>
- API 문서: <http://127.0.0.1:8000/docs>
- 키 인식 확인: <http://127.0.0.1:8000/api/health>

`/api/health` 응답의 `riot_api_configured`가 `true`이면 키가 정상적으로 읽힌 것입니다.

VS Code에서는 다음 방법도 사용할 수 있습니다.

- `Ctrl+Shift+P > Tasks: Run Task > Rift Signal 한국어판: 로컬 서버 실행`
- `Run and Debug` 화면에서 `Rift Signal 한국어판: FastAPI` 선택 후 `F5`

## 5. Vercel 최초 연결

먼저 Node.js와 npm이 보이는지 확인합니다.

```cmd
node -v
npm -v
```

Vercel CLI가 없다면 VS Code 터미널에서 한 번만 설치합니다.

```cmd
npm install -g vercel
```

로그인하고 현재 폴더를 Vercel 프로젝트와 연결합니다.

```cmd
vercel login
vercel link
```

Windows PowerShell에서 실행 정책 오류가 나면 `vercel` 대신 `vercel.cmd`를 사용합니다.

```powershell
vercel.cmd login
vercel.cmd link
```

이미 `.vercel` 폴더가 만들어져 있다면 프로젝트 연결은 완료된 상태입니다. `.vercel` 역시 Git에는 올라가지 않습니다.

VS Code 작업으로 실행할 수도 있습니다.

- `Rift Signal 한국어판: Vercel 로그인`
- `Rift Signal 한국어판: Vercel 프로젝트 연결`

### `'vercel'은(는) 내부 또는 외부 명령이 아닙니다` 해결

Conda 환경 때문이 아니라, VS Code가 실행될 당시의 `PATH`에 Node.js와 npm 전역 실행 폴더가 없어서 발생하는 문제입니다.

이 컴퓨터에서 확인된 설치 위치:

```text
Node.js: C:\Program Files\nodejs
Vercel:  C:\Users\dossa\AppData\Roaming\npm\vercel.cmd
```

가장 간단한 방법은 VS Code를 완전히 종료한 뒤 다시 열고 새 터미널을 만드는 것입니다. 그래도 인식되지 않으면 현재 CMD 터미널에서 다음 명령을 실행합니다.

```cmd
set "PATH=C:\Program Files\nodejs;C:\Users\dossa\AppData\Roaming\npm;%PATH%"
```

PowerShell 터미널에서는 다음과 같습니다.

```powershell
$env:Path = "C:\Program Files\nodejs;$env:APPDATA\npm;$env:Path"
```

설치 경로와 버전을 확인합니다.

```cmd
where node
where npm
where vercel
vercel --version
```

정상적으로 버전이 출력되면 아래의 키 등록 및 배포 명령을 계속 실행하면 됩니다. `set` 또는 `$env:Path`로 추가한 경로는 현재 터미널에만 적용됩니다.

## 6. Vercel에 Riot API 키 최초 등록

운영 환경에 `RIOT_API_KEY`가 아직 없을 때 한 번 실행합니다.

```cmd
vercel env add RIOT_API_KEY production --sensitive
```

Windows PowerShell에서:

```powershell
vercel.cmd env add RIOT_API_KEY production --sensitive
```

CLI가 값을 물으면 새 `RGAPI-...` 키를 붙여 넣습니다. 키를 명령줄 뒤에 직접 적지 않기 때문에 PowerShell 명령 기록에 값이 남지 않습니다.

등록 후 운영 배포를 실행합니다.

```cmd
vercel --prod
```

또는 VS Code 작업을 순서대로 실행합니다.

1. `Rift Signal 한국어판: Vercel에 Riot 키 최초 등록`
2. `Rift Signal 한국어판: 운영 배포`

## 7. 24시간마다 Vercel 키 교체

Riot 개발 키를 새로 발급받은 뒤 VS Code 터미널에서 실행합니다.

```cmd
vercel env update RIOT_API_KEY production --sensitive
vercel --prod
```

Windows PowerShell에서:

```powershell
vercel.cmd env update RIOT_API_KEY production --sensitive
vercel.cmd --prod
```

환경변수 변경은 이미 실행 중인 배포에 자동 반영되지 않으므로 반드시 새 운영 배포까지 해야 합니다.

VS Code에서는 `Ctrl+Shift+P > Tasks: Run Task > Rift Signal 한국어판: Riot 키 갱신 후 운영 배포` 하나만 실행하면 키 입력 후 순서대로 재배포됩니다.

로컬에서도 같은 키를 사용할 경우 `.env`의 값도 교체한 뒤 로컬 서버를 재시작합니다.

## 8. Vercel 웹 화면에서 교체하는 방법

CLI 대신 VS Code 브라우저나 일반 브라우저에서도 변경할 수 있습니다.

1. Vercel에서 `riot-player-analysis-kor` 프로젝트를 엽니다.
2. `Settings > Environment Variables`로 이동합니다.
3. `RIOT_API_KEY`를 편집하여 새 키로 교체합니다.
4. `Deployments`에서 최신 배포의 메뉴를 열고 `Redeploy`를 선택합니다.

## 9. Preview와 Development 환경에도 키가 필요한 경우

운영 주소만 사용할 때는 `production` 등록만으로 충분합니다. Vercel 미리보기 배포나 `vercel dev`에서도 라이브 Riot API를 사용하려면 각각 등록합니다.

```cmd
vercel env add RIOT_API_KEY preview --sensitive
vercel env add RIOT_API_KEY development --sensitive
```

이미 등록된 키를 교체할 때는 `add` 대신 `update`를 사용합니다.

```cmd
vercel env update RIOT_API_KEY preview --sensitive
vercel env update RIOT_API_KEY development --sensitive
```

## 10. 자주 생기는 문제

### `riot_api_configured`가 `false`

- `.env` 파일 이름이 정확한지 확인합니다.
- 키 앞뒤에 따옴표나 공백이 들어가지 않았는지 확인합니다.
- `python -m pip install -r requirements.txt`를 다시 실행합니다.
- 서버를 완전히 종료한 뒤 다시 실행합니다.

### Vercel에서 키를 바꿨는데 이전 키를 사용함

환경변수를 저장한 뒤 `vercel --prod` 또는 Vercel 화면의 `Redeploy`를 실행해야 합니다.

### `500 FUNCTION_INVOCATION_FAILED`

Vercel 함수가 시작될 때 Python 모듈이나 실행에 필요한 파일을 찾지 못하면 발생합니다. 이 프로젝트의 `vercel.json`은 템플릿, 정적 파일, 기준 데이터를 함수 번들에 포함하도록 설정되어 있습니다.

먼저 운영 버전을 다시 배포합니다.

```cmd
vercel --prod
```

그래도 실패하면 최근 함수 로그를 확인합니다.

```cmd
vercel logs https://riot-player-analysis-kor.vercel.app --since 30m --no-follow
```

### `'vercel'은(는) 내부 또는 외부 명령이 아닙니다`

현재 CMD 터미널의 `PATH`를 복구하고 다시 확인합니다.

```cmd
set "PATH=C:\Program Files\nodejs;C:\Users\dossa\AppData\Roaming\npm;%PATH%"
vercel --version
```

이후 원래 실행하려던 `vercel` 명령을 다시 실행합니다.

### `Environment Variable already exists`

최초 등록용 `add`가 아니라 갱신용 `update`를 사용합니다.

```cmd
vercel env update RIOT_API_KEY production --sensitive
```

### Riot API에서 401 또는 403 반환

개발 키가 만료되었거나 잘못 입력된 경우가 대부분입니다. Riot Developer Portal에서 새 키를 발급받아 로컬 `.env`와 Vercel 값을 갱신합니다.

### 키를 실수로 GitHub에 올림

즉시 Riot Developer Portal에서 해당 키를 폐기하고 새 키를 발급받습니다. 파일을 지우는 것만으로는 이전 Git 기록에서 키가 사라지지 않습니다.

## 11. 공개 운영 전 권장 사항

Riot 개발 키는 24시간짜리 테스트용입니다. 서비스를 계속 공개 운영하려면 Riot Production API Key를 신청하는 것이 좋습니다. 승인받은 운영 키로 전환하면 매일 개발 키를 교체하는 절차가 필요하지 않습니다.

## 주요 페이지

- `/`: 한국어 랜딩 페이지
- `/analysis`: Riot ID 기반 비교 분석 및 7일 훈련 루틴
- `/growth`: 루틴 달력, 성장 추이 및 분석 히스토리
- `/metrics`: 이전 주소 호환을 위해 `/growth`로 자동 이동
- `/docs`: FastAPI API 문서

## 프로젝트 구조

```text
main.py                 FastAPI 앱과 라우트
server.py               Vercel용 진입점
vercel.json             Vercel 함수 번들 설정
app/
  analytics.py          플레이어 및 벤치마크 계산
  config.py             경로와 환경변수 설정
  riot.py               Riot API 클라이언트와 CSV 캐시
templates/              Jinja2 페이지 템플릿
public/css/             반응형 스타일
public/js/              검색 및 분석 화면 동작
data/reference/         벤치마크 데이터
data/users/             Riot ID별 로컬 캐시
```
