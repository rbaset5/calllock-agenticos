"use client";

import { Html } from "@react-three/drei";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { useEffect, useMemo, useState } from "react";

type DailyMemoProps = {
  visible: boolean;
};

type DailyMemoDepartment = {
  name: string;
  items: string[];
};

type DailyMemoContent = {
  departments?: DailyMemoDepartment[];
};

type DailyMemoRow = {
  id: string;
  memo_date: string;
  content: DailyMemoContent;
  generated_at: string;
};

let browserClient: SupabaseClient | null = null;

function getSupabaseBrowserClient() {
  if (browserClient) {
    return browserClient;
  }

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!url || !anonKey) {
    return null;
  }

  browserClient = createClient(url, anonKey);
  return browserClient;
}

function formatDateKey(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function shiftDate(dateKey: string, amount: number) {
  const date = new Date(`${dateKey}T12:00:00`);
  date.setDate(date.getDate() + amount);
  return formatDateKey(date);
}

function formatLabel(dateKey: string) {
  return new Intl.DateTimeFormat("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(`${dateKey}T12:00:00`));
}

export default function DailyMemo({ visible }: DailyMemoProps) {
  const [selectedDate, setSelectedDate] = useState(() => formatDateKey(new Date()));
  const [memo, setMemo] = useState<DailyMemoRow | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  useEffect(() => {
    const client = getSupabaseBrowserClient();
    if (!client || !visible) {
      return;
    }

    let active = true;
    setLoading(true);
    setErrorMessage(null);

    void (async () => {
      const { data, error } = await client
        .from("daily_memo")
        .select("id, memo_date, content, generated_at")
        .eq("memo_date", selectedDate)
        .order("generated_at", { ascending: false })
        .limit(1)
        .maybeSingle();

      if (!active) {
        return;
      }

      if (error) {
        setErrorMessage(error.message);
        setMemo(null);
      } else {
        setMemo((data as DailyMemoRow | null) ?? null);
        const nextExpanded: Record<string, boolean> = {};
        for (const department of data?.content?.departments ?? []) {
          nextExpanded[department.name] = true;
        }
        setExpanded(nextExpanded);
      }

      if (active) {
        if (active) {
          setLoading(false);
        }
      }
    })();

    return () => {
      active = false;
    };
  }, [selectedDate, visible]);

  const departments = useMemo(
    () => memo?.content?.departments ?? [],
    [memo]
  );

  return (
    <group>
      <Html fullscreen style={{ pointerEvents: "none" }}>
        <aside
          className={`absolute bottom-6 left-6 w-[24rem] max-w-[calc(100vw-3rem)] transition ${
            visible
              ? "translate-y-0 opacity-100 pointer-events-auto"
              : "translate-y-3 opacity-0 pointer-events-none"
          }`}
        >
          <div className="rounded-[1.75rem] border border-white/10 bg-slate-950/80 p-4 shadow-2xl backdrop-blur-xl">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.28em] text-sky-300">
                  Daily Memo
                </p>
                <h2 className="mt-2 text-xl font-semibold text-white">
                  Department Briefing
                </h2>
              </div>
              <div className="rounded-full bg-white/10 px-3 py-1 text-xs text-slate-300">
                {memo ? "loaded" : "empty"}
              </div>
            </div>

            <div className="mt-4 flex items-center justify-between gap-3 rounded-2xl border border-white/10 bg-slate-900/60 px-3 py-3">
              <button
                type="button"
                onClick={() => setSelectedDate((value) => shiftDate(value, -1))}
                className="rounded-xl bg-white/5 px-3 py-2 text-sm text-slate-200 transition hover:bg-white/10"
              >
                Previous
              </button>
              <div className="text-center">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                  Selected Date
                </p>
                <p className="mt-1 text-sm font-medium text-white">
                  {formatLabel(selectedDate)}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedDate((value) => shiftDate(value, 1))}
                className="rounded-xl bg-white/5 px-3 py-2 text-sm text-slate-200 transition hover:bg-white/10"
              >
                Next
              </button>
            </div>

            {errorMessage ? (
              <div className="mt-4 rounded-2xl border border-rose-400/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-100">
                {errorMessage}
              </div>
            ) : null}

            <div className="mt-4 max-h-[26rem] space-y-3 overflow-y-auto pr-1">
              {loading ? (
                <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-4 text-sm text-slate-300">
                  Loading memo...
                </div>
              ) : departments.length > 0 ? (
                departments.map((department) => (
                  <section
                    key={department.name}
                    className="rounded-2xl border border-white/10 bg-slate-900/75"
                  >
                    <button
                      type="button"
                      onClick={() =>
                        setExpanded((current) => ({
                          ...current,
                          [department.name]: !current[department.name],
                        }))
                      }
                      className="flex w-full items-center justify-between px-4 py-3 text-left"
                    >
                      <span className="text-sm font-semibold text-white">
                        {department.name}
                      </span>
                      <span className="text-xs text-slate-400">
                        {expanded[department.name] ? "collapse" : "expand"}
                      </span>
                    </button>

                    {expanded[department.name] ? (
                      <div className="border-t border-white/10 px-4 py-3">
                        {department.items.length > 0 ? (
                          <ul className="space-y-2 text-sm leading-6 text-slate-200">
                            {department.items.map((item) => (
                              <li key={item} className="rounded-xl bg-white/5 px-3 py-2">
                                {item}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className="text-sm text-slate-400">
                            No updates recorded.
                          </p>
                        )}
                      </div>
                    ) : null}
                  </section>
                ))
              ) : (
                <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-4 text-sm text-slate-300">
                  No memo for this date
                </div>
              )}
            </div>
          </div>
        </aside>
      </Html>
    </group>
  );
}
