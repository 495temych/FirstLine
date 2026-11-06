import { useEffect, useState } from "react";

/** Fetch on mount and whenever `key` changes. */
export function useLoad<T>(load: () => Promise<T>, key?: unknown) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    let current = true;
    load()
      .then((value) => {
        if (current) setData(value);
      })
      .catch((reason: unknown) => {
        if (current) setError(String(reason).replace(/^Error: /, ""));
      });
    return () => {
      current = false;
    };
  }, [load, key]);

  return { data, error };
}
