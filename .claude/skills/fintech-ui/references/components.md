# 컴포넌트 참고

이 프로젝트에 **이미 있는** 컴포넌트 목록이다. 새로 만들기 전에 여기서 찾는다. 있는 걸 다시 만들면 스타일이 갈라지고, 나중에 색 하나 바꿀 때 두 군데를 고쳐야 한다.

정의는 전부 `static/css/style.css`에 있고, 아래는 어떤 게 있고 언제 쓰는지에 대한 목차다.

## 목차

- [레이아웃](#레이아웃)
- [카드](#카드)
- [버튼](#버튼)
- [폼](#폼)
- [표](#표)
- [탭](#탭)
- [다이얼로그](#다이얼로그)
- [피드백: 토스트 · 스피너](#피드백-토스트--스피너)
- [빈 상태](#빈-상태)
- [화면별 전용](#화면별-전용)
- [새 컴포넌트를 만들 때](#새-컴포넌트를-만들-때)

---

## 레이아웃

| 클래스 | 용도 |
|---|---|
| `.header` / `.header__inner` / `.header__brand` / `.header__logo` / `.header__title` | 상단 고정 헤더 |
| `.main` | 본문 영역. `--max-width`로 가운데 정렬 |
| `.section-header` / `__title` / `__desc` | 각 탭 최상단 제목 + 한 줄 설명 |
| `.section-header--row` | 제목과 컨트롤을 같은 줄에 둘 때 |

새 탭이나 섹션을 만들면 `.section-header`로 시작한다. 제목만 덩그러니 두지 말고 `__desc`로 이 화면이 뭘 하는지 한 줄 준다. 사용자는 탭 이름만으로 기능을 다 알지 못한다.

## 카드

| 클래스 | 용도 |
|---|---|
| `.card` | 기본 컨테이너. `--color-surface` 배경 + `--radius-md` + `--shadow-sm` |
| `.card__title` | 카드 안 소제목 |
| `.stat-card` / `__label` / `__value` | 숫자 하나를 크게 보여주는 카드 (이번 달 총 지출 등) |
| `.chart-wrapper` | 차트 캔버스를 감싸는 고정 높이 박스 |

**차트는 반드시 `.chart-wrapper` 안에 넣는다.** Chart.js는 `maintainAspectRatio: false`로 쓰고 있어서, 높이가 정해진 부모가 없으면 캔버스가 무한히 늘어난다.

`.stat-card__value`는 화면에서 가장 큰 글자다. 한 화면에 여러 개 두면 시선이 분산되니 개수를 늘리기 전에 정말 다 중요한지 따져본다.

## 버튼

| 클래스 | 용도 |
|---|---|
| `.btn` | 공통 기본형 (단독 사용 X, 수정자와 함께) |
| `.btn--primary` | 화면의 주요 동작. **섹션당 하나** |
| `.btn--outline` | 보조 동작 (다시 입력 등) |
| `.btn--full` | 가로 전체 너비 |
| `.btn--danger` | 되돌릴 수 없는 동작(삭제). `--color-error` 배경 |

주요 동작이 둘이면 사용자는 무엇을 눌러야 할지 멈춰서 생각한다. "저장하기"가 `--primary`면 "다시 입력"은 `--outline`이어야 한다.

파괴적 동작(삭제 등)은 `--color-error`를 쓰되, **기본 포커스는 안전한 쪽**에 둔다.

## 폼

| 클래스 | 용도 |
|---|---|
| `.form-label` | 입력 라벨 |
| `.form-input` / `.form-input--search` | 한 줄 입력 / 검색창 |
| `.form-textarea` | 문자 붙여넣기 같은 여러 줄 입력 |
| `.form-select` | 드롭다운 |
| `.form-select--inline` | 다른 값들과 한 줄에 놓이는 드롭다운 (미리보기 카테고리). 16px·44px 보장 |
| `.filter-bar` | 필터 컨트롤 가로 배치 |
| `.list-summary` | 목록 위 건수 한 줄 (`2026년 10월 · 7건`) |
| `.month-picker` | 월 선택 |

입력창에는 `placeholder`로 **실제 예시**를 넣는다. 문자 입력창이 `[신한카드] 승인 12,000원 ...` 형식을 보여주는 이유는, 사용자가 뭘 붙여넣어야 하는지 설명 없이 알게 하기 위해서다.

검색처럼 입력할 때마다 반응하는 필드는 `debounce()`(`utils.js`)로 감싼다. 안 그러면 글자마다 요청이 나가고 로딩 오버레이가 깜빡인다.

## 표

| 클래스 | 용도 |
|---|---|
| `.table-wrapper` | 가로 넘침 처리 |
| `.table` | 본체 |
| `.table__amount-col` | 금액 열 (우측 정렬) |
| `.table__empty-row` | 빈 결과 행. 안에 `createEmptyState()`를 넣는다 |
| `.table__row--clickable` / `.table__store-btn` | 누르면 상세가 열리는 행 / 그 행의 상점명 버튼 (키보드·스크린리더용) |

**금액은 오른쪽 정렬**한다. 자릿수가 세로로 맞아야 크기 비교가 눈으로 된다.

**칸은 기본적으로 줄바꿈하지 않는다**(`white-space: nowrap`). `☕ 카/페`, `12,000/원`처럼 끊기면 읽을 수 없다. 줄바꿈은 상점명 칸(`td:nth-child(2)`)만 단어 단위로 허용하고, 이 칸이 남는 폭을 가져간다. 열을 추가하거나 순서를 바꾸면 이 선택자도 같이 고친다. 375px에서 칸이 모자라면 줄바꿈을 풀기 전에 반복되는 정보부터 줄인다 (예: 월로 걸러진 목록은 날짜를 `formatShortDate()`로 `10.14`만 표시).

행을 그릴 때 사용자 데이터(상점명)는 `textContent`로 넣는다. `innerHTML` 템플릿 문자열에 끼워 넣으면 조작된 문자로 스크립트가 실행될 수 있다.

빈 결과에는 반드시 `.table__empty-row`를 쓴다. `<tbody>`를 비워두면 고장처럼 보인다.

표에 넣을 자리가 없는 정보(시간·카드사)와 행 단위 동작(삭제)은 **열을 늘리지 말고 행을 눌러 여는 다이얼로그**에 둔다. 행 전체에 클릭을 걸되, 키보드로도 열 수 있게 칸 하나는 `<button>`으로 만든다.

## 다이얼로그

| 클래스 | 용도 |
|---|---|
| `.dialog` / `__body` / `__title` / `__amount` / `__list` / `__row` / `__note` / `__actions` | 거래 상세 (`<dialog>` + `showModal()`) |

네이티브 `<dialog>`를 쓴다. Esc 닫기와 포커스 가두기가 기본으로 된다. 배경은 `--color-overlay`이고, 내용은 `.dialog__body` 안에 둬서 **배경을 누를 때만** `e.target === dialog`가 되게 한다.

- **처음 포커스는 안전한 버튼**에 둔다 (`autofocus`를 "닫기"에). 파괴적 버튼은 `.btn--danger`로 쓰고, 무슨 일이 일어나는지를 버튼 글자에 쓴다 ("삭제").
- 다이얼로그는 top layer라서 **열린 채로는 로딩 오버레이·토스트가 그 뒤에 가려진다.** 요청을 보내기 전에 먼저 `close()`한다.
- `alert()` / `confirm()`은 쓰지 않는다. 버튼 글자를 바꿀 수 없어 "확인"만 보인다.

## 탭

| 클래스 | 용도 |
|---|---|
| `.tab-nav` / `__item` / `__item--active` / `__icon` / `__label` | 하단 고정 탭 바 |
| `.tab-content` / `--active` | 탭별 화면 |

연결은 `data-tab`(버튼) ↔ `data-tab-content`(섹션) 속성으로 한다. `main.js`의 `switchTab()`이 이 쌍을 찾아 클래스와 `aria-selected`를 갱신한다. 다른 곳에서 탭을 바꿀 때도 클래스를 직접 만지지 말고 `switchTab()`을 쓴다. **새 탭을 추가하면 양쪽 속성을 모두** 넣어야 한다.

탭 바는 `position: fixed`라 `body`의 `padding-bottom: var(--tab-nav-height)`에 의존한다. 이걸 건드리면 마지막 콘텐츠가 가려진다.

## 피드백: 토스트 · 스피너

| 클래스 | 용도 |
|---|---|
| `.toast` / `--success` / `--error` | 하단 알림 |
| `.loading-overlay` / `.loading-spinner` | 전체 화면 로딩 |

JS에서 직접 클래스를 만지지 말고 `utils.js`의 함수를 쓴다:

```js
showToast('저장됐어요! ✅', 'success');
showToast(err.message, 'error');   // 백엔드가 보낸 실제 원인을 띄운다
showLoading(true);                  // finally에서 반드시 showLoading(false)
```

`showLoading`은 호출 횟수를 세므로 요청이 겹쳐도 안전하다. 다만 **켠 만큼 꺼야** 한다. `try/finally`로 짝을 맞춘다.

`[hidden]` 숨김은 `style.css` 리셋 블록의 `[hidden] { display: none !important }`에 의존한다. `.loading-overlay`가 `display: flex`라서 이게 없으면 오버레이가 화면을 계속 덮는다. 이 규칙을 지우지 않는다.

## 빈 상태

| 클래스 | 용도 |
|---|---|
| `.empty-state` / `__title` / `__desc` / `__action` | 데이터가 없을 때 안내 + 다음 할 일 버튼 |

직접 마크업하지 말고 `utils.js`의 `createEmptyState()`로 만든다. `textContent`로 채우므로 안전하다:

```js
container.replaceChildren(createEmptyState({
  title:  `${formatMonth(month)}에는 아직 지출 내역이 없어요`,
  desc:   '결제 문자를 입력하면 카테고리별·일별 차트가 여기에 그려져요',
  action: { label: '문자 입력하러 가기', tab: 'input' },  // 생략 가능
}));
```

`action.tab`은 버튼의 `data-go-tab`이 되고, `main.js`가 document 위임으로 받아 `switchTab()`을 호출한다. **필터 때문에 비었을 때는 버튼 없이 "조건을 바꿔보세요"로 안내**한다. 그 상황에서 "문자 입력하러 가기"는 엉뚱한 해결책이다.

## 화면별 전용

| 클래스 | 화면 |
|---|---|
| `.parse-result__*` (`header`, `store`, `amount`, `badge`, `meta`, `meta-item`, `meta-label`, `meta-value`, `actions`) | 탭1 파싱 미리보기 |
| `.peer-summary__*` (`item`, `divider`, `label`, `value`, `value--muted`) | 탭4 내 지출 vs 또래 평균 |
| `.advice-card__*` (`header`, `icon`, `title`, `text`) | 탭4 AI 조언 |

`.parse-result`는 **저장 전 미리보기**다. 여기 보이는 건 아직 DB에 없다. 사용자가 확인하고 고칠 기회를 주는 자리이므로, 파싱 결과를 그대로 저장해버리는 흐름으로 바꾸지 않는다.

`.peer-summary__value--muted`는 또래 평균 쪽에 쓴다. 내 지출이 주인공이고 또래는 비교 기준이라 시각적 무게가 같으면 안 된다. 또래 데이터가 없을 땐 `0원` 대신 "데이터 없음"을 넣는다 — 0원은 "또래는 한 푼도 안 쓴다"로 읽힌다.

## 새 컴포넌트를 만들 때

1. 위 목록에 비슷한 게 있는지 먼저 본다. `.card`로 해결되는 경우가 많다.
2. 이름은 BEM 느슨하게: `블록__요소--수정자`.
3. 색·반경·그림자는 `:root` 토큰만 쓴다. 새 색이 꼭 필요하면 토큰으로 추가하고 이유를 주석에 남긴다.
4. 여백·글자 크기는 SKILL.md의 계단값에서 고른다.
5. 375px 폭에서 확인한다.
6. 로딩 / 빈 상태 / 에러 / 성공 네 가지를 같이 만든다.
