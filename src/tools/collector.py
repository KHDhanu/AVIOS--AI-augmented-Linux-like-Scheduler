#!/usr/bin/env python3

"""
collector.py
Collect per-process Linux PCB-style features into a CSV.

Usage:
sudo python3 collector.py --interval 1.0 --out linux_dataset.csv
"""

import psutil, time, csv, os, argparse
from datetime import datetime


def read_proc_sched(pid):
    path = f"/proc/{pid}/sched"
    d = {}
    try:
        with open(path, "r") as f:
            for line in f:
                parts = line.strip().split(":")
                if len(parts) != 2:
                    continue
                key, val = parts
                key = key.strip().replace(" ", "_")
                val = val.strip().split()[0]
                # select only a few keys
                if key in [
                    "se.exec_start", "se.vruntime", "se.sum_exec_runtime",
                    "nr_switches", "nr_voluntary_switches",
                    "nr_involuntary_switches", "se.load.weight"
                ]:
                    d[key] = val
        return d
    except Exception:
        return {}


def get_sched_policy(pid):
    try:
        pol = os.sched_getscheduler(pid)
        mp = {
            0: "SCHED_OTHER", 1: "SCHED_FIFO", 2: "SCHED_RR",
            3: "SCHED_BATCH", 5: "SCHED_IDLE"
        }
        return mp.get(pol, str(pol))
    except Exception:
        return ""


def sample_once(clock_ticks):
    rows = []
    now = datetime.now().isoformat()
    for p in psutil.process_iter(['pid', 'name', 'ppid', 'num_threads',
                                  'status', 'cmdline']):
        try:
            pid = p.info['pid']
            pname = p.info.get('name') or ""
            pppid = p.info.get('ppid') or -1
            threads = p.info.get('num_threads') or 0
            state = p.info.get('status') or ""
            cmdline = " ".join(p.info.get('cmdline') or [])

            # memory
            mem_info = p.memory_info()
            vmrss = int(mem_info.rss / 1024)
            vmsize = int(mem_info.vms / 1024)

            # cpu
            cpu_pct = p.cpu_percent(interval=None)
            t = p.cpu_times()
            total_time_ticks = int((t.user + t.system) * clock_ticks)
            elapsed = time.time() - p.create_time()

            # context switches
            cs = p.num_ctx_switches()
            vol = cs.voluntary
            invol = cs.involuntary

            # nice/priority
            nice = p.nice()
            # priority from /proc/<pid>/stat
            prio = None
            try:
                with open(f"/proc/{pid}/stat") as f:
                    parts = f.read().split()
                    prio = int(parts[17])  # field 18 = priority
            except:
                pass

            # scheduling policy
            sched_pol = get_sched_policy(pid)

            # sched stats
            schedstats = read_proc_sched(pid)

            # io
            io = p.io_counters()
            read_bytes = io.read_bytes
            write_bytes = io.write_bytes
            read_count = io.read_count
            write_count = io.write_count

            row = {
                "Timestamp": now,
                "PID": pid,
                "Name": pname,
                "Cmdline": cmdline,
                "PPid": pppid,
                "State": state,
                "Threads": threads,
                "Priority": prio,
                "Nice": nice,
                "Scheduling_Policy": sched_pol,
                "CPU_Usage_%": cpu_pct,
                "Total_Time_Ticks": total_time_ticks,
                "Elapsed_Time_sec": elapsed,
                "VmRSS": vmrss,
                "VmSize": vmsize,
                "Voluntary_ctxt_switches": vol,
                "Nonvoluntary_ctxt_switches": invol,
                "IO_Read_Bytes": read_bytes,
                "IO_Write_Bytes": write_bytes,
                "IO_Read_Count": read_count,
                "IO_Write_Count": write_count,
                # sched stats
                "se.exec_start": schedstats.get("se.exec_start"),
                "se.vruntime": schedstats.get("se.vruntime"),
                "se.sum_exec_runtime": schedstats.get("se.sum_exec_runtime"),
                "nr_switches": schedstats.get("nr_switches"),
                "nr_voluntary_switches": schedstats.get("nr_voluntary_switches"),
                "nr_involuntary_switches": schedstats.get("nr_involuntary_switches"),
                "se.load.weight": schedstats.get("se.load.weight"),
            }
            rows.append(row)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=float, default=1.0,
                        help="sampling interval seconds")
    parser.add_argument("--out", type=str, default="linux_dataset.csv")
    args = parser.parse_args()

    clock_ticks = os.sysconf(os.sysconf_names['SC_CLK_TCK'])

    fieldnames = [
        "Timestamp", "PID", "Name", "Cmdline", "PPid",
        "State", "Threads", "Priority", "Nice", "Scheduling_Policy",
        "CPU_Usage_%", "Total_Time_Ticks", "Elapsed_Time_sec",
        "VmRSS", "VmSize",
        "Voluntary_ctxt_switches", "Nonvoluntary_ctxt_switches",
        "IO_Read_Bytes", "IO_Write_Bytes", "IO_Read_Count", "IO_Write_Count",
        "se.exec_start", "se.vruntime", "se.sum_exec_runtime",
        "nr_switches", "nr_voluntary_switches", "nr_involuntary_switches",
        "se.load.weight"
    ]

    # create file with header if not exists
    if not os.path.exists(args.out):
        with open(args.out, "w", newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

    print(f"Starting collector. Writing to {args.out}. Press Ctrl-C to stop.")
    # warmup cpu_percent
    for p in psutil.process_iter():
        try:
            p.cpu_percent(interval=None)
        except:
            pass

    try:
        while True:
            rows = sample_once(clock_ticks)
            with open(args.out, "a", newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                for r in rows:
                    writer.writerow(r)
            print(f"{datetime.now().isoformat()} wrote {len(rows)} rows")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Stopping collector.")


if __name__ == "__main__":
    main()
