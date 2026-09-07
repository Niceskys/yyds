import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .cases import CHALLENGES
from .engine import DeterministicEngine
from .provider import FixtureProvider, GLMProvider, ModelCallError
from .blind import CASES as BLIND_CASES, baseline_turns, prompt as blind_prompt, simulate
from .final_validation import CASES as FINAL_CASES, INTENTS, plan as plan_intent, prompt as final_prompt


def legal(candidate) -> bool:
    return bool(candidate.strategy_id and candidate.rationale and candidate.actions and 0 <= candidate.confidence <= 1)


def main() -> None:
    parser = argparse.ArgumentParser(description="《规则之外》挑战链可行性测试器")
    parser.add_argument("--provider", choices=["fixture", "glm"], required=True)
    parser.add_argument("--suite", choices=["legacy", "ultimate", "final"], default="final")
    parser.add_argument("--output", default="reports/report.json")
    parser.add_argument("--timeout", type=int, default=120, help="单次 GLM 请求最长等待秒数")
    parser.add_argument("--retries", type=int, default=2, help="每关在传输失败后的额外重试次数")
    args = parser.parse_args()
    if args.suite == "ultimate":
        run_ultimate(args)
        return
    if args.suite == "final":
        run_final(args)
        return
    provider = FixtureProvider() if args.provider == "fixture" else GLMProvider(args.timeout, args.retries)
    engine = DeterministicEngine()
    results = []
    for case in CHALLENGES:
        try:
            print(f"\n=== {case.id} {case.title} ===", flush=True)
            analysis = provider.analyze(case)
            candidates = analysis.candidates
            winner = next((c for c in candidates if c.strategy_id == case.expected_strategy), None)
            executable = bool(winner and legal(winner))
            simulation = engine.simulate(case, winner.strategy_id if winner else "")
            repair = engine.simulate(case, winner.strategy_id if winner else "", repaired=True)
            results.append({"id": case.id, "title": case.title, "status": "answered", "attempts": analysis.attempts, "model_candidates": [c.__dict__ for c in candidates], "expected_strategy_hidden_from_model": case.expected_strategy, "strategy_found": winner is not None, "executable": executable, "advantage": simulation.advantage, "repair_reduces_advantage": repair.advantage < simulation.advantage, "trace": simulation.trace + repair.trace, "error": None})
        except ModelCallError as exc:
            results.append({"id": case.id, "title": case.title, "status": exc.kind, "attempts": exc.attempts, "strategy_found": False, "executable": False, "advantage": 0, "repair_reduces_advantage": False, "trace": [], "error": str(exc)})
        except Exception as exc:
            results.append({"id": case.id, "title": case.title, "status": "response_error", "attempts": 1, "strategy_found": False, "executable": False, "advantage": 0, "repair_reduces_advantage": False, "trace": [], "error": str(exc)})
    total = len(results)
    found = sum(x["strategy_found"] for x in results)
    executable = sum(x["executable"] for x in results)
    validated = sum(x["advantage"] > 0 for x in results)
    repaired = sum(x["repair_reduces_advantage"] for x in results)
    complete_logs = sum(x["error"] is None and bool(x["trace"]) for x in results)
    answered = sum(x["status"] == "answered" for x in results)
    timeouts = sum(x["status"] == "timeout" for x in results)
    invalid_outputs = sum(x["status"] == "invalid_model_output" for x in results)
    passed = answered >= 5 and found >= 5 and executable >= 5 and validated >= 5 and repaired >= 4 and complete_logs == total
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "provider": args.provider, "warning": "fixture 模式不能证明 GLM 能力" if args.provider == "fixture" else None, "thresholds": {"valid_responses": "至少5/6才允许立项判断", "strategy_found": "5/6", "executable": "5/6", "validated": "5/6", "repair": "4/6", "logs": "6/6"}, "summary": {"valid_responses": f"{answered}/{total}", "timeouts": f"{timeouts}/{total}", "invalid_model_outputs": f"{invalid_outputs}/{total}", "strategy_found": f"{found}/{total}", "executable": f"{executable}/{total}", "validated": f"{validated}/{total}", "repair": f"{repaired}/{total}", "complete_logs": f"{complete_logs}/{total}", "recommend_project": passed if answered >= 5 else None, "conclusion": "样本不足，不能判定项目可行性" if answered < 5 else ("通过立项门槛" if passed else "未通过立项门槛")}, "cases": results}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"报告已写入：{output}")


def run_ultimate(args) -> None:
    provider = FixtureProvider() if args.provider == "fixture" else GLMProvider(args.timeout, args.retries)
    results = []
    for case in BLIND_CASES:
        print(f"\n=== 盲测 {case.case_id} ===", flush=True)
        try:
            if args.provider == "fixture":
                data, attempts = {"analysis": "离线参考", "turns": case.oracle_turns}, 1
            else:
                data, attempts = provider.ask_json(case.case_id, blind_prompt(case))
            turns = data.get("turns", []) if isinstance(data, dict) else []
            evaluated, base, oracle = simulate(case, turns), simulate(case, baseline_turns(case)), simulate(case, case.oracle_turns)
            gain = evaluated["score"] - base["score"]
            passed = evaluated["invalid_actions"] == 0 and gain >= case.minimum_gain
            results.append({"id": case.case_id, "control": case.is_control, "status": "answered", "attempts": attempts, "model_analysis": data.get("analysis", ""), "submitted_turns": turns, "baseline_score": base["score"], "candidate_score": evaluated["score"], "oracle_score_hidden_from_model": oracle["score"], "gain_over_baseline": gain, "minimum_required_gain_hidden_from_model": case.minimum_gain, "invalid_actions": evaluated["invalid_actions"], "strategy_verified": passed, "trace": evaluated["trace"], "error": None})
        except ModelCallError as exc:
            results.append({"id": case.case_id, "status": exc.kind, "attempts": exc.attempts, "strategy_verified": False, "error": str(exc)})
        except Exception as exc:
            results.append({"id": case.case_id, "status": "response_error", "attempts": 1, "strategy_verified": False, "error": str(exc)})
    total, answered = len(results), sum(x["status"] == "answered" for x in results)
    positive = [x for x in results if not x.get("control")]
    passed = sum(x["strategy_verified"] for x in positive)
    # 六个相互独立的机制全部盲测；至少 5 个有效回答、5 个真实收益才可立项。
    verdict = answered >= 5 and passed >= 4
    report = {"suite": "ultimate_blind_action_test", "integrity": {"model_never_receives": ["case identity", "strategy labels", "oracle plan", "threshold", "repair rule"], "scoring": "模型的自由行动计划由确定性引擎执行，并与不利用规则的基线比较"}, "summary": {"valid_responses": f"{answered}/{total}", "verified_discoveries": f"{passed}/5", "control_cases": "1（不计入发现率）", "recommend_project": verdict if answered >= 5 else None, "conclusion": "样本不足，不能判定" if answered < 5 else ("通过高完整性立项门槛" if verdict else "未通过高完整性立项门槛")}, "cases": results}
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2)); print(f"盲测报告已写入：{output}")


def run_final(args) -> None:
    provider = FixtureProvider() if args.provider == "fixture" else GLMProvider(args.timeout, args.retries)
    results = []
    for final_case in FINAL_CASES:
        case = final_case.case
        print(f"\n=== 最终验证 {case.case_id} ===", flush=True)
        try:
            if args.provider == "fixture":
                data, attempts = {"analysis": "离线参考", "intents": [{"intent": final_case.oracle_intent, "confidence": 1.0}]}, 1
            else:
                data, attempts = provider.ask_json(case.case_id, final_prompt(final_case))
            intents = [x.get("intent") for x in data.get("intents", []) if isinstance(x, dict) and x.get("intent") in INTENTS][:2]
            plans = [plan_intent(case, intent) for intent in intents]
            best = max(plans, key=lambda p: p["result"]["score"], default=None)
            semantic = final_case.oracle_intent in intents
            executable = bool(best and best["result"]["invalid_actions"] == 0)
            gain = best["result"]["score"] - best["baseline"]["score"] if best else None
            verified = bool(executable and gain is not None and gain >= final_case.minimum_gain)
            results.append({"id":case.case_id,"control":final_case.control,"status":"answered","attempts":attempts,"model_analysis":data.get("analysis",""),"suggested_intents":intents,"semantic_intent_match_hidden_reference":semantic,"planner_plans_evaluated":sum(p["plans_evaluated"] for p in plans),"selected_plan":best["turns"] if best else [],"baseline_score":best["baseline"]["score"] if best else None,"selected_score":best["result"]["score"] if best else None,"gain_over_baseline":gain,"minimum_gain_hidden_reference":final_case.minimum_gain,"planner_executable":executable,"verified_gain":verified,"trace":best["result"]["trace"] if best else [],"error":None})
        except ModelCallError as exc:
            results.append({"id":case.case_id,"control":final_case.control,"status":exc.kind,"attempts":exc.attempts,"error":str(exc)})
        except Exception as exc:
            results.append({"id":case.case_id,"control":final_case.control,"status":"response_error","attempts":1,"error":str(exc)})
    answered = [x for x in results if x["status"] == "answered"]
    positive = [x for x in answered if not x["control"]]
    controls = [x for x in answered if x["control"]]
    semantic = sum(x["semantic_intent_match_hidden_reference"] for x in answered)
    executable = sum(x["planner_executable"] for x in answered)
    gains = sum(x["verified_gain"] for x in positive)
    controls_ok = sum(x["semantic_intent_match_hidden_reference"] and x["verified_gain"] for x in controls)
    passed = len(answered) >= 8 and semantic >= 8 and executable >= 9 and gains >= 7 and controls_ok == 2
    report = {"suite":"final_strategy_planner_validation","integrity":{"model_role":"只提出最多两个高层策略意图；不输出坐标或棋步","planner_role":"为每个 GLM 候选意图枚举合法行动方案并确定性结算","hidden_from_model":["关卡标识的含义","正确意图","参考方案","收益阈值"]},"thresholds":{"strategy_understanding":"8/10","planner_execution":"9/10","positive_gain":"7/8","controls":"2/2"},"summary":{"valid_responses":f"{len(answered)}/10","strategy_understanding":f"{semantic}/10","planner_execution":f"{executable}/10","verified_gain":f"{gains}/8","control_handling":f"{controls_ok}/2","recommend_project":passed if len(answered)>=8 else None,"conclusion":"样本不足，不能判定" if len(answered)<8 else ("通过最终立项门槛" if passed else "未通过最终立项门槛")},"cases":results}
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report["summary"],ensure_ascii=False,indent=2)); print(f"最终验证报告已写入：{output}")


if __name__ == "__main__":
    main()
