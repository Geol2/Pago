import Link from "next/link";

export default function Home() {
  const features = [
    {
      title: "퍼널 분석 자동화",
      text: "유입부터 결제 완료까지 단계별 전환 저하 구간을 자동 식별하고, 원인 후보를 근거 데이터와 함께 제시합니다.",
    },
    {
      title: "이상 징후 탐지",
      text: "전환율 급락, 결제 실패율 상승, 채널별 편차 확대를 실시간으로 감지해 빠른 원인 분석을 지원합니다.",
    },
    {
      title: "실행 가능한 리포트",
      text: "지표 변화와 가설 검증 결과를 한 화면에 정리해 마케팅, 기획, 개발이 같은 기준으로 의사결정할 수 있게 합니다.",
    },
  ];

  const steps = [
    "데이터 소스 연결",
    "핵심 KPI 정의",
    "자동 분석 실행",
    "인사이트 공유",
  ];

  return (
    <div className="relative min-h-screen overflow-hidden bg-slate-950 text-slate-100">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_15%_20%,#0ea5e950,transparent_35%),radial-gradient(circle_at_85%_10%,#f59e0b45,transparent_40%),radial-gradient(circle_at_80%_80%,#10b98130,transparent_35%)]" />

      <main className="relative mx-auto flex w-full max-w-6xl flex-col gap-12 px-6 py-10 sm:px-10 lg:px-12 lg:py-14">
        <header className="flex items-center">
          <p className="text-sm font-semibold tracking-[0.22em] text-sky-300">PAGO ANALYTICS</p>
        </header>

        <section className="reveal grid items-center gap-8 lg:grid-cols-[1.15fr_0.85fr]">
          <div className="reveal-stagger space-y-6">
            <p className="inline-flex rounded-full border border-sky-300/30 bg-sky-300/10 px-3 py-1 text-xs font-semibold tracking-wide text-sky-200">
              Analysis Tool Introduction
            </p>
            <h1 className="text-4xl font-black leading-tight sm:text-5xl lg:text-6xl">
              지표를 보는 화면이 아니라,
              <br />
              원인을 설명하는 분석 환경
            </h1>
            <p className="max-w-xl text-base leading-7 text-slate-300 sm:text-lg">
              Pago Analytics는 결제, 유입, 전환 데이터를 하나로 연결해
              &quot;무엇이, 언제, 왜 바뀌었는지&quot;를 재현 가능한 방식으로 정리합니다.
              팀은 감이 아닌 데이터 근거로 우선순위를 정하고 실험 결과를 빠르게 검증할 수 있습니다.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link
                href="/trial"
                className="rounded-xl bg-sky-400 px-5 py-3 text-sm font-bold text-slate-950 transition hover:bg-sky-300"
              >
                분석 환경 시작
              </Link>
              <Link
                href="/docs"
                className="rounded-xl border border-slate-600 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:border-amber-300 hover:text-amber-200"
              >
                분석 기능 문서 보기
              </Link>
            </div>
          </div>

          <div className="reveal rounded-2xl border border-slate-800 bg-slate-900/70 p-5 backdrop-blur">
            <p className="mb-4 text-sm font-semibold text-slate-300">분석 운영 지표 예시</p>
            <div className="space-y-4">
              <div>
                <div className="mb-1 flex items-center justify-between text-xs text-slate-400">
                  <span>이슈 분석 소요 시간</span>
                  <span>-64%</span>
                </div>
                <div className="h-2 rounded-full bg-slate-800">
                  <div className="h-2 w-[64%] rounded-full bg-emerald-400" />
                </div>
              </div>
              <div>
                <div className="mb-1 flex items-center justify-between text-xs text-slate-400">
                  <span>가설 검증 반복 속도</span>
                  <span>+2.3x</span>
                </div>
                <div className="h-2 rounded-full bg-slate-800">
                  <div className="h-2 w-[78%] rounded-full bg-sky-400" />
                </div>
              </div>
              <div className="rounded-xl bg-slate-800/70 p-4">
                <p className="text-xs text-slate-400">주간 분석 리포트 생성 수</p>
                <p className="mt-1 text-2xl font-extrabold tracking-tight">42 reports</p>
              </div>
            </div>
          </div>
        </section>

        <section className="reveal grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => (
            <article
              key={feature.title}
              className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 transition hover:-translate-y-1 hover:border-sky-300/50"
            >
              <h2 className="text-lg font-bold">{feature.title}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-300">{feature.text}</p>
            </article>
          ))}
        </section>

        <section className="reveal rounded-2xl border border-slate-800 bg-slate-900/60 p-5 sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-xs font-semibold tracking-wide text-amber-200">ANALYSIS WORKFLOW</p>
              <h2 className="mt-2 text-2xl font-extrabold">3일 안에 분석 루프 구축</h2>
            </div>
            <Link
              href="/contact"
              className="rounded-xl bg-amber-300 px-5 py-3 text-sm font-bold text-slate-950 transition hover:bg-amber-200"
            >
              분석 세팅 상담
            </Link>
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {steps.map((step, idx) => (
              <div key={step} className="rounded-xl border border-slate-800 bg-slate-900 p-4">
                <p className="text-xs font-semibold text-sky-300">STEP {idx + 1}</p>
                <p className="mt-2 text-sm font-semibold">{step}</p>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
