"use client";

import { useEffect } from "react";
import Link from "next/link";
import { trackEvent } from "../../lib/tracking";

export default function TrialPage() {
  useEffect(() => {
    trackEvent("page_view", {
      page: "trial",
      source: "landing",
    });
  }, []);

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-12 text-slate-100 sm:px-10">
      <div className="reveal mx-auto max-w-3xl rounded-2xl border border-slate-800 bg-slate-900/70 p-8">
        <p className="text-xs font-semibold tracking-[0.2em] text-emerald-300">ANALYSIS TRIAL</p>
        <h1 className="mt-3 text-3xl font-black">Pago Analytics 분석 체험</h1>
        <p className="mt-4 text-sm leading-7 text-slate-300 sm:text-base">
          14일 체험 기간 동안 핵심 KPI를 정의하고, 지표 변동 원인을 추적하는 분석 루틴을 실제 데이터로 검증할 수 있습니다.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/trial/connect-db"
            onClick={() =>
              trackEvent("trial_cta_click", {
                page: "trial",
                cta: "connect_db",
              })
            }
            className="rounded-xl bg-emerald-400 px-5 py-3 text-sm font-bold text-slate-950 transition hover:bg-emerald-300"
          >
            DB 연결 시작
          </Link>
          <Link
            href="/contact"
            onClick={() =>
              trackEvent("trial_cta_click", {
                page: "trial",
                cta: "consultation",
              })
            }
            className="rounded-xl border border-slate-700 px-5 py-3 text-sm font-semibold transition hover:border-slate-500"
          >
            상담 문의
          </Link>
          <Link
            href="/"
            onClick={() =>
              trackEvent("trial_cta_click", {
                page: "trial",
                cta: "back_home",
              })
            }
            className="rounded-xl border border-slate-700 px-5 py-3 text-sm font-semibold transition hover:border-slate-500"
          >
            홈으로 돌아가기
          </Link>
        </div>
      </div>
    </main>
  );
}
