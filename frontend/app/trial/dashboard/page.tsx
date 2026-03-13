"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { trackEvent } from "../../../lib/tracking";

type DatabaseType = "postgresql" | "mysql" | "mssql";

type ConnectionForm = {
  dbType: DatabaseType;
  host: string;
  port: string;
  dbName: string;
  username: string;
  password: string;
  schema: string;
  ssl: boolean;
  savedAt?: number;
};

type TableInfo = {
  schema: string;
  name: string;
};

export default function TrialDashboardPage() {
  const router = useRouter();
  const [connection, setConnection] = useState<ConnectionForm | null>(null);
  const [tables, setTables] = useState<TableInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [message, setMessage] = useState("연결 정보를 확인하는 중입니다...");

  const hasConnection = useMemo(() => connection !== null, [connection]);

  const loadTables = useCallback(async (conn: ConnectionForm) => {
    setIsLoading(true);
    setMessage("테이블 목록을 불러오는 중입니다...");

    try {
      const response = await fetch("/api/db/list-tables", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(conn),
      });

      const data = (await response.json()) as {
        ok: boolean;
        message: string;
        tables?: TableInfo[];
        count?: number;
      };

      if (response.ok && data.ok) {
        const nextTables = data.tables ?? [];
        setTables(nextTables);
        setMessage(`${data.message} (${data.count ?? nextTables.length}개)`);
        trackEvent("db_tables_dashboard_result", {
          page: "trial_dashboard",
          result: "success",
          count: data.count ?? nextTables.length,
          db_type: conn.dbType,
        });
      } else {
        setTables([]);
        setMessage(data.message || "테이블 조회 실패");
        trackEvent("db_tables_dashboard_result", {
          page: "trial_dashboard",
          result: "failed",
          db_type: conn.dbType,
        });
      }
    } catch {
      setTables([]);
      setMessage("테이블 조회 실패: 네트워크 또는 서버 상태를 확인해 주세요.");
      trackEvent("db_tables_dashboard_result", {
        page: "trial_dashboard",
        result: "request_error",
        db_type: conn.dbType,
      });
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const raw = sessionStorage.getItem("pago-db-connection");

    if (!raw) {
      setConnection(null);
      setTables([]);
      setMessage("연결 정보가 없습니다. 먼저 DB 연결 페이지에서 테스트를 완료해 주세요.");
      setIsLoading(false);
      return;
    }

    try {
      const parsed = JSON.parse(raw) as ConnectionForm;
      setConnection(parsed);
      trackEvent("db_dashboard_view", {
        page: "trial_dashboard",
        db_type: parsed.dbType,
      });
      void loadTables(parsed);
    } catch {
      setConnection(null);
      setTables([]);
      setMessage("연결 정보를 읽을 수 없습니다. 다시 연결해 주세요.");
      setIsLoading(false);
    }
  }, [loadTables]);

  const refreshTables = () => {
    if (!connection) {
      return;
    }

    trackEvent("db_tables_dashboard_refresh", {
      page: "trial_dashboard",
      db_type: connection.dbType,
    });
    void loadTables(connection);
  };

  const reconnect = () => {
    router.push("/trial/connect-db");
  };

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-10 text-slate-100 sm:px-10 lg:px-12">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-5">
        <section className="reveal rounded-2xl border border-slate-800 bg-slate-900/70 p-6 sm:p-7">
          <p className="text-xs font-semibold tracking-[0.2em] text-sky-300">ANALYSIS DASHBOARD</p>
          <h1 className="mt-3 text-3xl font-black">테이블 분석 대시보드</h1>
          <p className="mt-3 text-sm text-slate-300">
            연결된 데이터베이스의 테이블 목록을 확인하고 분석 대상을 빠르게 파악할 수 있습니다.
          </p>

          <div className="mt-5 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={refreshTables}
              disabled={!hasConnection || isLoading}
              className="rounded-xl bg-sky-400 px-5 py-3 text-sm font-bold text-slate-950 transition hover:bg-sky-300 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isLoading ? "불러오는 중..." : "테이블 새로고침"}
            </button>
            <button
              type="button"
              onClick={reconnect}
              className="rounded-xl border border-slate-700 px-5 py-3 text-sm font-semibold transition hover:border-slate-500"
            >
              연결 정보 다시 입력
            </button>
            <Link
              href="/trial"
              className="rounded-xl border border-slate-700 px-5 py-3 text-sm font-semibold transition hover:border-slate-500"
            >
              체험 페이지로 돌아가기
            </Link>
          </div>
        </section>

        <section className="reveal rounded-2xl border border-slate-800 bg-slate-900/70 p-6 sm:p-7">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-lg font-bold">연결 정보</h2>
            <span className="text-xs text-slate-400">
              {connection ? `${connection.dbType} | ${connection.host}:${connection.port} | ${connection.dbName}` : "미연결"}
            </span>
          </div>

          <p className="text-sm text-slate-300">{message}</p>

          {tables.length > 0 ? (
            <div className="mt-4 overflow-hidden rounded-xl border border-slate-800">
              <table className="w-full border-collapse text-left text-sm">
                <thead className="bg-slate-900 text-slate-300">
                  <tr>
                    <th className="px-4 py-3 font-semibold">Schema</th>
                    <th className="px-4 py-3 font-semibold">Table</th>
                  </tr>
                </thead>
                <tbody>
                  {tables.map((table) => (
                    <tr key={`${table.schema}.${table.name}`} className="border-t border-slate-800 bg-slate-950/70">
                      <td className="px-4 py-3 text-slate-400">{table.schema}</td>
                      <td className="px-4 py-3 text-slate-100">{table.name}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950 p-4 text-sm text-slate-400">
              표시할 테이블이 없습니다.
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
