import asyncio
import random
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, List, Optional

from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register


@register(
    "qq_member_verify",
    "SodaTide",
    "QQ群成员动态验证插件 (group_verification)",
    "26.4.17",
    "基于 https://github.com/huntuo146/astrbot_plugin_Group-Verification_PRO 修改"
)
class QQGroupVerifyPlugin(Star):
    def __init__(self, context: Context, config: Dict[str, Any]):
        super().__init__(context)
        self.context = context

        # --- 分群启用配置 ---
        raw_groups = config.get("enabled_groups", [])
        self.enabled_groups: List[str] = [str(g) for g in raw_groups] if raw_groups else []

        # --- 时间控制 ---
        self.verification_timeout = int(config.get("verification_timeout", 300))
        self.time_based_timeouts = config.get("time_based_timeouts", [])
        self.kick_countdown_warning_time = int(config.get("kick_countdown_warning_time", 60))
        self.kick_delay = int(config.get("kick_delay", 5))
        
        # --- 自动撤回无关消息配置 ---
        self.auto_recall_irrelevant_messages = bool(config.get("auto_recall_irrelevant_messages", False))
        self.auto_recall_threshold = max(0, int(config.get("auto_recall_threshold", 1)))
        self.auto_recall_bot_messages = bool(config.get("auto_recall_bot_messages", False))

        # --- 自动审批补验配置 ---
        self.auto_approval_verify_only = bool(config.get("auto_approval_verify_only", False))
        self.auto_approval_window_minutes = max(1, int(config.get("auto_approval_window_minutes", 1)))
        self.join_request_cache_ttl_seconds = max(
            60,
            int(
                config.get(
                    "join_request_cache_ttl_seconds",
                    self.auto_approval_window_minutes * 60 + 300,
                )
            ),
        )
        self.auto_approval_ignore_time_based_bypass = bool(
            config.get("auto_approval_ignore_time_based_bypass", True)
        )
        self.auto_approval_lookup_system_msg = bool(
            config.get("auto_approval_lookup_system_msg", True)
        )
        self.auto_approval_system_msg_retry_delay = float(
            config.get("auto_approval_system_msg_retry_delay", 1.0)
        )
        self.auto_approval_nickname_match = bool(
            config.get("auto_approval_nickname_match", True)
        )

        # --- 低 QQ 等级强制验证 ---
        self.low_qq_level_force_verify_threshold = int(
            config.get("low_qq_level_force_verify_threshold", -1)
        )
        self.low_qq_level_force_verify_timeout = int(
            config.get("low_qq_level_force_verify_timeout", -1)
        )

        # --- 防刷屏与失败控制 ---
        self.max_failed_attempts = int(config.get("max_failed_attempts", 0))
        self.max_unverified_messages = int(config.get("max_unverified_messages", 0))
        self.unverified_reminder_count = int(config.get("unverified_reminder_count", 0))

        # --- 问答库与验证模式配置 ---
        raw_qa = config.get("custom_qa", []) 
        self.question_bank: Dict[str, List[str]] = {}
        for item in raw_qa:
            if "=" in str(item):
                q, a = str(item).split("=", 1)
                self.question_bank[q.strip()] = [k.strip() for k in a.split(",") if k.strip()]

        self.qa_probability = float(config.get("qa_probability", 0.5))
        self.switch_to_math_on_failure = bool(config.get("switch_to_math_on_failure", True))
        self.allow_answer_without_at = bool(config.get("allow_answer_without_at", False))
        self.wrong_answer_bypass_behavior = str(
            config.get("wrong_answer_bypass_behavior", "pass")
        ).strip().lower()
        if self.wrong_answer_bypass_behavior not in {"pass", "continue"}:
            logger.warning(
                f"[QQ Verify] 未知 wrong_answer_bypass_behavior={self.wrong_answer_bypass_behavior}，已回退为 pass。"
            )
            self.wrong_answer_bypass_behavior = "pass"

        # --- LLM 开放题配置 ---
        self.llm_question_enabled = bool(config.get("llm_question_enabled", False))
        self.llm_provider_id = str(config.get("llm_provider_id", "")).strip()
        self.llm_evaluation_timeout = int(config.get("llm_evaluation_timeout", 30))
        self.llm_error_behavior = str(
            config.get("llm_error_behavior", "pass")
        ).strip().lower()
        if self.llm_error_behavior not in {"pass", "retry_math"}:
            logger.warning(
                f"[QQ Verify] 未知 llm_error_behavior={self.llm_error_behavior}，已回退为 pass。"
            )
            self.llm_error_behavior = "pass"
        self.llm_timeout_buffer = int(config.get("llm_timeout_buffer", 120))
        self.llm_system_prompt = config.get(
            "llm_system_prompt",
            "你是一个群聊验证助手。请根据题目和关键词评估用户的回答是否合理。回答应言之有理，与题目相关。",
        )
        self.llm_evaluation_prompt = config.get(
            "llm_evaluation_prompt",
            "题目：{question}\n关键词参考：{keywords}\n用户回答：{answer}\n请判断用户回答是否合理，只回复 'PASS' 或 'FAIL'。",
        )

        # --- 自定义消息模板 ---
        self.new_member_prompt = config.get("new_member_prompt", "{at_user} 欢迎加入本群！请在 {timeout} 分钟内 @我 并回答下面的问题以完成验证：\n{question}")
        self.welcome_message = config.get("welcome_message", "{at_user} 验证成功，欢迎你的加入！")
        self.bypass_welcome_message = config.get(
            "bypass_welcome_message",
            "{at_user} 当前处于免验证时段，已结束本次验证流程。欢迎入群！",
        )
        self.wrong_answer_prompt = config.get("wrong_answer_prompt", "{at_user} 答案错误，请重新回答验证。这是你的新问题：\n{question}")
        self.countdown_warning_prompt = config.get("countdown_warning_prompt", "{at_user} 验证即将超时，请尽快查看我的验证消息进行人机验证！")
        self.failure_message = config.get("failure_message", "{at_user} 验证超时，你将在 {countdown} 秒后被请出本群。")
        self.kick_message = config.get("kick_message", "{at_user} 因未在规定时间内完成验证，已被请出本群。")
        self.unverified_reminder_prompt = config.get("unverified_reminder_prompt", "{at_user} 提醒：你已发送多条无关消息，请尽快 @我 回答下面的问题完成验证，否则将被踢出本群！\n{question}")

        # 待处理的验证状态记录
        self.pending: Dict[str, Dict[str, Any]] = {}

        # 入群申请缓存（用于识别“申请后短时间内自动通过”的成员）
        self.join_requests: Dict[str, Dict[str, Any]] = {}

    def _is_group_enabled(self, gid: int) -> bool:
        if not self.enabled_groups:
            return True
        return str(gid) in self.enabled_groups

    def _get_current_timeout(self) -> Optional[int]:
        if not self.time_based_timeouts:
            return self.verification_timeout

        now = datetime.now()
        current_minutes = now.hour * 60 + now.minute

        for rule in self.time_based_timeouts:
            try:
                time_part, timeout_part = str(rule).split("=")
                start_str, end_str = time_part.split("-")
                timeout_val = int(timeout_part.strip())

                start_h, start_m = map(int, start_str.strip().split(":"))
                end_h, end_m = map(int, end_str.strip().split(":"))

                start_mins = start_h * 60 + start_m
                end_mins = end_h * 60 + end_m

                if start_mins <= end_mins:
                    matched = start_mins <= current_minutes <= end_mins
                else:
                    matched = current_minutes >= start_mins or current_minutes <= end_mins

                if matched:
                    if timeout_val == -1:
                        return None
                    return timeout_val
            except Exception as e:
                logger.warning(f"[QQ Verify] 解析时间段规则失败: {rule}, 错误: {e}")
                continue

        return self.verification_timeout

    def _create_pending_key(self, gid: int, uid: str) -> str:
        return f"{gid}:{uid}"

    def _create_join_request_key(self, gid: int, uid: str) -> str:
        return f"{gid}:{uid}"

    def _cleanup_expired_join_requests(self):
        if not self.join_requests:
            return

        now = datetime.now()
        expired_keys = [
            key
            for key, info in self.join_requests.items()
            if now - info.get("request_time", now) > timedelta(seconds=self.join_request_cache_ttl_seconds)
        ]
        for key in expired_keys:
            self.join_requests.pop(key, None)

    def _store_join_request(self, gid: int, uid: str, raw: Dict[str, Any]):
        self._cleanup_expired_join_requests()
        request_key = self._create_join_request_key(gid, uid)
        self.join_requests[request_key] = {
            "request_time": datetime.now(),
            "flag": raw.get("flag"),
            "comment": raw.get("comment"),
        }
        logger.info(f"[QQ Verify] 已记录用户 {uid} 在群 {gid} 的入群申请事件。")

    def _consume_join_request_match(self, gid: int, uid: str) -> Tuple[bool, Optional[float]]:
        self._cleanup_expired_join_requests()
        request_key = self._create_join_request_key(gid, uid)
        request_info = self.join_requests.pop(request_key, None)
        if not request_info:
            return False, None

        request_time = request_info.get("request_time")
        if not isinstance(request_time, datetime):
            return False, None

        elapsed_seconds = max(0.0, (datetime.now() - request_time).total_seconds())
        matched = elapsed_seconds <= self.auto_approval_window_minutes * 60
        return matched, elapsed_seconds

    async def _get_low_qq_level(self, event: AstrMessageEvent, uid: str) -> Optional[int]:
        if self.low_qq_level_force_verify_threshold < 0:
            return None

        try:
            result = await event.bot.api.call_action("get_stranger_info", user_id=int(uid))
        except Exception as e:
            logger.warning(f"[QQ Verify] 查询用户 {uid} 的 QQ 等级失败: {e}")
            return None

        if not isinstance(result, dict):
            logger.warning(f"[QQ Verify] 查询用户 {uid} 的 QQ 等级失败: 返回结果不是字典。")
            return None

        data = result.get("data", result)
        if not isinstance(data, dict):
            logger.warning(f"[QQ Verify] 查询用户 {uid} 的 QQ 等级失败: data 字段无效。")
            return None

        qq_level = data.get("qqLevel")
        if qq_level is None:
            logger.warning(f"[QQ Verify] 查询用户 {uid} 的 QQ 等级失败: 缺少 qqLevel 字段。")
            return None

        try:
            return int(str(qq_level).strip())
        except Exception:
            logger.warning(f"[QQ Verify] 查询用户 {uid} 的 QQ 等级失败: qqLevel={qq_level!r} 无法解析。")
            return None

    def _resolve_low_qq_force_timeout(self) -> int:
        if self.low_qq_level_force_verify_timeout > 0:
            return self.low_qq_level_force_verify_timeout
        return self.verification_timeout

    def _extract_timestamp_from_request_id(self, request_id: Any) -> Optional[float]:
        request_id_str = str(request_id).strip()
        if not request_id_str.isdigit() or len(request_id_str) < 10:
            return None
        try:
            return float(int(request_id_str[:10]))
        except Exception:
            return None

    async def _lookup_auto_approved_from_system_msg(self, event: AstrMessageEvent, gid: int, uid: str, nickname: str = "") -> Tuple[bool, Optional[float]]:
        if not self.auto_approval_lookup_system_msg:
            return False, None

        async def _query_once() -> Tuple[bool, Optional[float]]:
            try:
                result = await event.bot.api.call_action("get_group_system_msg")
            except Exception as e:
                logger.warning(f"[QQ Verify] 查询群系统消息失败: {e}")
                return False, None

            if not isinstance(result, dict):
                return False, None

            data = result.get("data", result)
            if not isinstance(data, dict):
                return False, None

            join_requests = data.get("join_requests", [])
            if not isinstance(join_requests, list):
                return False, None

            now_ts = datetime.now().timestamp()
            target_gid = str(gid)
            target_uid = str(uid)
            normalized_nickname = str(nickname or "").strip()
            best_score = -1
            best_elapsed: Optional[float] = None
            best_reason = ""

            for item in join_requests:
                if not isinstance(item, dict):
                    continue
                if str(item.get("group_id")) != target_gid:
                    continue
                if not item.get("checked"):
                    continue

                request_ts = self._extract_timestamp_from_request_id(item.get("request_id"))
                if request_ts is None:
                    continue

                elapsed_seconds = max(0.0, now_ts - request_ts)
                if elapsed_seconds > self.auto_approval_window_minutes * 60:
                    continue

                invitor_uin = str(item.get("invitor_uin", "")).strip()
                invitor_nick = str(item.get("invitor_nick", "")).strip()
                requester_nick = str(item.get("requester_nick", "")).strip()
                score = 0
                reasons: List[str] = []

                if invitor_uin and invitor_uin == target_uid:
                    score += 3
                    reasons.append("uin")

                if self.auto_approval_nickname_match and normalized_nickname:
                    if requester_nick and requester_nick == normalized_nickname:
                        score += 2
                        reasons.append("requester_nick")
                    if invitor_nick and requester_nick and invitor_nick == requester_nick:
                        score += 1
                        reasons.append("invitor_eq_requester")

                if elapsed_seconds <= 5:
                    score += 2
                    reasons.append("time<=5s")
                elif elapsed_seconds <= 30:
                    score += 1
                    reasons.append("time<=30s")

                if score >= 4 and score > best_score:
                    best_score = score
                    best_elapsed = elapsed_seconds
                    best_reason = "+".join(reasons)

            if best_elapsed is None:
                return False, None

            logger.info(
                f"[QQ Verify] 用户 {uid} 在群 {gid} 通过 get_group_system_msg 命中自动审批补验窗口，"
                f"耗时 {best_elapsed:.1f} 秒，匹配依据: {best_reason or 'score'}。"
            )
            return True, best_elapsed

        matched, elapsed_seconds = await _query_once()
        if matched:
            return matched, elapsed_seconds

        if self.auto_approval_system_msg_retry_delay > 0:
            await asyncio.sleep(self.auto_approval_system_msg_retry_delay)
            return await _query_once()

        return False, None

    async def _recall_tracked_messages(self, bot_api, pending_key: str, gid: int, uid: str, reason: str):
        """撤回用户未验证期间发送的消息（保留用于兼容性）"""
        state = self.pending.get(pending_key)
        if not state:
            return
    
        message_ids = state.get("message_ids", [])
        if not message_ids:
            return
    
        recalled_count = 0
        for message_id in message_ids:
            try:
                await bot_api.call_action("delete_msg", message_id=message_id)
                recalled_count += 1
            except Exception as e:
                logger.warning(f"[QQ Verify] 撤回用户 {uid} 在群 {gid} 的消息 {message_id} 失败: {e}")
    
        if recalled_count > 0:
            logger.info(f"[QQ Verify] 用户 {uid} 在群 {gid} 因[{reason}]共撤回 {recalled_count} 条未验证期间消息。")
    
    async def _recall_bot_messages(self, bot_api, pending_key: str, gid: int, uid: str, reason: str):
        """撤回机器人发送的验证消息"""
        if not self.auto_recall_bot_messages:
            return
    
        state = self.pending.get(pending_key)
        if not state:
            return
    
        bot_message_ids = state.get("bot_message_ids", [])
        if not bot_message_ids:
            return
    
        recalled_count = 0
        for message_id in bot_message_ids:
            try:
                await bot_api.call_action("delete_msg", message_id=message_id)
                recalled_count += 1
            except Exception as e:
                logger.warning(f"[QQ Verify] 撤回机器人消息 {message_id} 失败: {e}")
    
        if recalled_count > 0:
            logger.info(f"[QQ Verify] 用户 {uid} 在群 {gid} 因[{reason}]共撤回 {recalled_count} 条机器人验证消息。")

    def _track_pending_message(self, pending_key: str, message_id: Any):
        if message_id is None:
            return
        state = self.pending.get(pending_key)
        if not state:
            return
        tracked_message_ids = state.setdefault("message_ids", [])
        if message_id not in tracked_message_ids:
            tracked_message_ids.append(message_id)
    
    def _track_bot_message(self, pending_key: str, message_id: Any):
        """跟踪机器人发送的验证消息ID，用于后续撤回"""
        if message_id is None:
            return
        state = self.pending.get(pending_key)
        if not state:
            return
        tracked_bot_message_ids = state.setdefault("bot_message_ids", [])
        if message_id not in tracked_bot_message_ids:
            tracked_bot_message_ids.append(message_id)

    async def _clear_pending_state(self, bot_api, pending_key: str, gid: int, uid: str, reason: str, recall_messages: bool = True):
        state = self.pending.get(pending_key)
        if not state:
            return
    
        task = state.get("task")
        if task and not task.done() and task != asyncio.current_task():
            task.cancel()
    
        if recall_messages:
            await self._recall_tracked_messages(bot_api, pending_key, gid, uid, reason)
    
        # 撤回机器人验证消息
        await self._recall_bot_messages(bot_api, pending_key, gid, uid, reason)
    
        self.pending.pop(pending_key, None)

    async def _send_welcome_message(self, bot_api, gid: int, uid: str, nickname: str, message_template: str):
        if not message_template or not message_template.strip():
            return
    
        welcome_msg = message_template.format(
            at_user=f"[CQ:at,qq={uid}]",
            member_name=nickname,
        )
        result = await bot_api.call_action("send_group_msg", group_id=gid, message=welcome_msg)
        # 跟踪机器人发送的验证消息ID
        if result and isinstance(result, dict):
            bot_msg_id = result.get("message_id")
            if bot_msg_id:
                pending_key = self._create_pending_key(gid, uid)
                self._track_bot_message(pending_key, bot_msg_id)

    async def _evaluate_llm_answer(self, question: str, keywords: List[str], answer: str) -> bool:
        """调用 LLM 评估用户回答是否合理
        
        Args:
            question: 验证题目
            keywords: 关键词列表，供 LLM 参考
            answer: 用户的回答
            
        Returns:
            bool: True 表示通过评估，False 表示未通过
        """
        # 构建评估提示词
        keywords_str = "、".join(keywords) if keywords else "无特定关键词"
        eval_prompt = self.llm_evaluation_prompt.format(
            question=question,
            keywords=keywords_str,
            answer=answer,
        )
        system_prompt = self.llm_system_prompt.format(
            question=question,
            keywords=keywords_str,
        )
        
        # 获取 provider ID
        provider_id = self.llm_provider_id if self.llm_provider_id else None
        
        try:
            logger.info(f"[QQ Verify] 开始 LLM 评估，题目: {question}，用户回答: {answer[:50]}...")
            
            if provider_id:
                # 使用指定的 provider
                llm_resp = await self.context.llm_generate(
                    chat_provider_id=provider_id,
                    prompt=eval_prompt,
                    system_prompt=system_prompt,
                )
            else:
                # 使用默认 provider（需要 umo，这里用空字符串回退）
                # 尝试获取当前会话的 provider
                try:
                    # 这里没有 event 对象，所以使用 context 的默认方法
                    # 如果 llm_provider_id 为空，使用空字符串让 llm_generate 使用默认
                    llm_resp = await self.context.llm_generate(
                        chat_provider_id="",
                        prompt=eval_prompt,
                        system_prompt=system_prompt,
                    )
                except Exception as e:
                    logger.warning(f"[QQ Verify] 使用默认 provider 失败，尝试使用 get_using_provider: {e}")
                    # 回退到传统方法
                    provider = self.context.get_using_provider()
                    if provider:
                        resp = await provider.text_chat(
                            prompt=eval_prompt,
                            system_prompt=system_prompt,
                        )
                        llm_resp = resp
                    else:
                        logger.error("[QQ Verify] 无法获取 LLM provider，LLM 评估失败")
                        return self._handle_llm_error()
            
            if llm_resp is None:
                logger.warning("[QQ Verify] LLM 评估返回为空")
                return self._handle_llm_error()
            
            response_text = getattr(llm_resp, "completion_text", "")
            if not response_text:
                # 尝试其他可能的属性
                response_text = str(llm_resp)
            
            logger.info(f"[QQ Verify] LLM 评估原始响应: {response_text[:100]}")
            
            # 判断是否通过评估
            passed = "PASS" in response_text.upper()
            
            if passed:
                logger.info("[QQ Verify] LLM 评估结果: PASS（通过）")
            else:
                logger.info("[QQ Verify] LLM 评估结果: FAIL（未通过）")
            
            return passed
            
        except asyncio.TimeoutError:
            logger.warning(f"[QQ Verify] LLM 评估超时（{self.llm_evaluation_timeout}秒）")
            return self._handle_llm_error()
        except Exception as e:
            logger.error(f"[QQ Verify] LLM 评估调用失败: {e}")
            return self._handle_llm_error()

    def _handle_llm_error(self) -> bool:
        """处理 LLM 调用错误的情况
        
        Returns:
            bool: 根据配置决定是放行（True）还是需要重新答题（False）
        """
        if self.llm_error_behavior == "pass":
            logger.info("[QQ Verify] LLM 调用失败，配置为放行")
            return True
        else:
            logger.info("[QQ Verify] LLM 调用失败，配置为切换数学题")
            return False

    def _generate_question(self, force_math: bool = False) -> Tuple[str, Any, str]:
        # 如果强制使用数学题，直接生成
        if force_math:
            op_type = random.choice(['add', 'sub'])
            if op_type == 'add':
                num1 = random.randint(0, 100)
                num2 = random.randint(0, 100 - num1)
                answer = num1 + num2
                question = f"{num1} + {num2} = ?"
            else:
                num1 = random.randint(1, 100)
                num2 = random.randint(0, num1)
                answer = num1 - num2
                question = f"{num1} - {num2} = ?"
            return question, answer, "math"
        
        # 根据 qa_probability 决定使用问答题库还是数学题
        use_qa = bool(self.question_bank) and (random.random() < self.qa_probability)
        if use_qa:
            # 筛选可用题目：如果 LLM 功能未启用，则排除 llm: 前缀的题目
            available_questions = [
                q for q in self.question_bank.keys()
                if self.llm_question_enabled or not q.lower().startswith("llm:")
            ]
            if available_questions:
                question = random.choice(available_questions)
                answer_data = self.question_bank[question]
                # 判断题目类型
                if question.lower().startswith("llm:"):
                    # LLM 题目格式: llm:题目=关键词1,关键词2 或 llm:题目
                    if "=" in question:
                        q_part, a_part = question.split("=", 1)
                        q_clean = q_part[4:].strip()  # 去掉 "llm:" 前缀
                        keywords = [k.strip() for k in a_part.split(",") if k.strip()]
                        return q_clean, keywords, "llm"
                    else:
                        q_clean = question[4:].strip()
                        return q_clean, [], "llm"
                else:
                    # 普通关键词题目
                    return question, answer_data, "qa"
        
        # 使用数学题
        op_type = random.choice(['add', 'sub'])
        if op_type == 'add':
            num1 = random.randint(0, 100)
            num2 = random.randint(0, 100 - num1)
            answer = num1 + num2
            question = f"{num1} + {num2} = ?"
        else:
            num1 = random.randint(1, 100)
            num2 = random.randint(0, num1)
            answer = num1 - num2
            question = f"{num1} - {num2} = ?"
        return question, answer, "math"

    @filter.event_message_type(filter.EventMessageType.ALL, priority=1919810)
    async def handle_event(self, event: AstrMessageEvent):
        if event.get_platform_name() != "aiocqhttp": return
        if not event.message_obj or not event.message_obj.raw_message: return
        raw = event.message_obj.raw_message
        if not isinstance(raw, dict): return

        post_type = raw.get("post_type")
        gid = raw.get("group_id")
        
        if post_type == "request":
            if raw.get("request_type") == "group" and raw.get("sub_type") == "add":
                if gid and not self._is_group_enabled(gid): return
                await self._process_join_request(event)

        elif post_type == "notice":
            notice_type = raw.get("notice_type")
            if notice_type == "group_increase":
                if gid and not self._is_group_enabled(gid): return
                if str(raw.get("user_id")) == str(event.get_self_id()): return
                await self._process_new_member(event)
            elif notice_type == "group_decrease":
                await self._process_member_decrease(event)
        
        elif post_type == "message" and raw.get("message_type") == "group":
            if gid and not self._is_group_enabled(gid): return
            await self._process_verification_message(event)

    async def _process_join_request(self, event: AstrMessageEvent):
        raw = event.message_obj.raw_message
        gid = raw.get("group_id")
        uid = str(raw.get("user_id"))
        if not gid or not uid:
            return
        self._store_join_request(gid, uid, raw)

    async def _process_new_member(self, event: AstrMessageEvent):
        raw = event.message_obj.raw_message
        uid = str(raw.get("user_id"))
        gid = raw.get("group_id")
        if not gid:
            return

        nickname = raw.get("user_name") or raw.get("nickname") or uid
        matched_auto_approval, elapsed_seconds = self._consume_join_request_match(gid, uid)
        if not matched_auto_approval:
            matched_auto_approval, elapsed_seconds = await self._lookup_auto_approved_from_system_msg(event, gid, uid, nickname=nickname)

        qq_level = await self._get_low_qq_level(event, uid)
        low_qq_force_verify = (
            qq_level is not None
            and self.low_qq_level_force_verify_threshold >= 0
            and qq_level <= self.low_qq_level_force_verify_threshold
        )

        if low_qq_force_verify:
            timeout_seconds = self._resolve_low_qq_force_timeout()
            logger.info(
                f"[QQ Verify] 用户 {uid} 在群 {gid} 的 QQ 等级为 {qq_level}，"
                f"命中低等级强制验证阈值 {self.low_qq_level_force_verify_threshold}，"
                f"已忽略分时段/自动审批放行规则并按 {timeout_seconds} 秒发起验证。"
            )
            if matched_auto_approval and elapsed_seconds is not None:
                logger.info(
                    f"[QQ Verify] 用户 {uid} 在群 {gid} 虽命中 {self.auto_approval_window_minutes} 分钟自动审批补验窗口"
                    f"（耗时 {elapsed_seconds:.1f} 秒），但低 QQ 等级强制验证优先。"
                )
            await self._start_verification_process(event, uid, gid, timeout_seconds=timeout_seconds, is_new_member=True)
            return

        timeout_seconds = self._get_current_timeout()
        in_time_based_bypass = timeout_seconds is None

        if matched_auto_approval:
            logger.info(
                f"[QQ Verify] 用户 {uid} 在群 {gid} 从申请到入群耗时 {elapsed_seconds:.1f} 秒，"
                f"命中 {self.auto_approval_window_minutes} 分钟自动审批补验窗口。"
            )
            if in_time_based_bypass and self.auto_approval_ignore_time_based_bypass:
                timeout_seconds = self.verification_timeout
                in_time_based_bypass = False
                logger.info(
                    f"[QQ Verify] 用户 {uid} 在群 {gid} 为自动快速通过成员，"
                    f"已忽略免验证时间段并按默认超时 {timeout_seconds} 秒发起验证。"
                )
        elif self.auto_approval_verify_only and in_time_based_bypass:
            logger.info(f"[QQ Verify] 用户 {uid} 在群 {gid} 未命中自动审批快速通过窗口，且当前为免验证时段，已跳过验证。")
            return

        if in_time_based_bypass or timeout_seconds is None:
            logger.info(f"[QQ Verify] 用户 {uid} 在群 {gid} 命中免验证时间段，已跳过验证流程。")
            return

        if timeout_seconds is None:
            logger.info(f"[QQ Verify] 用户 {uid} 在群 {gid} 当前未获得有效超时时间，已跳过验证流程。")
            return

        await self._start_verification_process(event, uid, gid, timeout_seconds=timeout_seconds, is_new_member=True)

    async def _start_verification_process(self, event: AstrMessageEvent, uid: str, gid: int, timeout_seconds: int, is_new_member: bool, force_math: bool = False):
        pending_key = self._create_pending_key(gid, uid)
        failed_count = 0
        unverified_count = 0
        message_ids: List[int] = []

        if pending_key in self.pending:
            failed_count = self.pending[pending_key].get("failed_attempts", 0)
            unverified_count = self.pending[pending_key].get("unverified_messages", 0)
            message_ids = list(self.pending[pending_key].get("message_ids", []))
            old_task = self.pending[pending_key].get("task")
            if old_task and not old_task.done():
                old_task.cancel()

        question, answer_data, q_type = self._generate_question(force_math)
        
        # LLM 开放题增加超时缓冲
        effective_timeout = timeout_seconds
        if q_type == "llm":
            effective_timeout = timeout_seconds + self.llm_timeout_buffer
            logger.info(f"[QQ Verify] LLM 开放题，基础超时 {timeout_seconds} 秒 + 缓冲 {self.llm_timeout_buffer} 秒 = {effective_timeout} 秒")
        
        logger.info(f"[QQ Verify] 为用户 {uid} 生成[{q_type}]问题: {question}，超时限制: {effective_timeout}秒")

        nickname = uid
        try:
            user_info = await event.bot.api.call_action("get_group_member_info", group_id=gid, user_id=int(uid))
            nickname = user_info.get("card", "") or user_info.get("nickname", uid)
        except Exception:
            pass

        expires_at = datetime.now() + timedelta(seconds=effective_timeout)
        task = asyncio.create_task(self._timeout_kick(uid, gid, nickname, effective_timeout, expires_at))

        # 将 question 存入 pending 字典中，方便后续调用
        self.pending[pending_key] = {
            "gid": gid, "uid": uid, "question": question, "answer": answer_data, "q_type": q_type, "task": task,
            "failed_attempts": failed_count, "unverified_messages": unverified_count, "message_ids": message_ids,
            "expires_at": expires_at, "session_timeout_seconds": effective_timeout,
        }

        at_user = f"[CQ:at,qq={uid}]"
        
        if is_new_member:
            timeout_minutes = max(1, effective_timeout // 60)
            prompt_message = self.new_member_prompt.format(at_user=at_user, member_name=nickname, question=question, timeout=timeout_minutes)
        else:
            prompt_message = self.wrong_answer_prompt.format(at_user=at_user, question=question)

        if prompt_message.strip():
            result = await event.bot.api.call_action("send_group_msg", group_id=gid, message=prompt_message)
            # 跟踪机器人发送的验证消息ID，用于后续撤回
            if result and isinstance(result, dict):
                bot_msg_id = result.get("message_id")
                if bot_msg_id:
                    self._track_bot_message(pending_key, bot_msg_id)

    async def _execute_kick(self, bot_api, gid: int, uid: str, nickname: str, reason: str, expected_expires_at: Optional[datetime] = None):
        pending_key = self._create_pending_key(gid, uid)
        state = self.pending.get(pending_key)
        if not state:
            logger.info(f"[QQ Verify] 用户 {uid} 在群 {gid} 因[{reason}]执行踢出前状态已清除，取消踢出。")
            return

        current_expires_at = state.get("expires_at")
        if expected_expires_at is not None and current_expires_at != expected_expires_at:
            logger.info(
                f"[QQ Verify] 用户 {uid} 在群 {gid} 因[{reason}]执行踢出前验证状态已更新，"
                f"取消本次踢出。"
            )
            return

        if reason == "验证超时":
            if not isinstance(current_expires_at, datetime):
                logger.warning(f"[QQ Verify] 用户 {uid} 在群 {gid} 缺少 expires_at，取消超时踢出以避免误踢。")
                return
            if datetime.now() < current_expires_at:
                logger.info(
                    f"[QQ Verify] 用户 {uid} 在群 {gid} 因[{reason}]执行踢出时尚未到最终截止时间，"
                    f"取消本次踢出。"
                )
                return

        await self._clear_pending_state(bot_api, pending_key, gid, uid, reason, recall_messages=True)

        try:
            await bot_api.call_action("set_group_kick", group_id=gid, user_id=int(uid), reject_add_request=False)
            logger.info(f"[QQ Verify] 用户 {uid} ({nickname}) 因[{reason}]被踢出群 {gid}。")

            if self.kick_message and self.kick_message.strip():
                at_user = f"[CQ:at,qq={uid}]"
                kick_msg = self.kick_message.format(at_user=at_user, member_name=nickname)
                result = await bot_api.call_action("send_group_msg", group_id=gid, message=kick_msg)
                # 跟踪机器人发送的验证消息ID
                if result and isinstance(result, dict):
                    bot_msg_id = result.get("message_id")
                    if bot_msg_id:
                        self._track_bot_message(pending_key, bot_msg_id)
        except Exception as e:
            logger.error(f"[QQ Verify] 踢人失败 (权限不足?): {e}")

    async def _process_verification_message(self, event: AstrMessageEvent):
        uid = str(event.get_sender_id())
        raw = event.message_obj.raw_message
        current_gid = raw.get("group_id")
        if not current_gid:
            return

        pending_key = self._create_pending_key(current_gid, uid)
        if pending_key not in self.pending:
            return

        text = event.message_str.strip()
        gid = self.pending[pending_key]["gid"]

        if str(current_gid) != str(gid): return

        nickname = raw.get("sender", {}).get("card", "") or raw.get("sender", {}).get("nickname", uid)
        bot_id = str(event.get_self_id())
        
        at_me = False
        if isinstance(raw.get("message"), list):
            for seg in raw.get("message"):
                if seg.get("type") == "at" and str(seg.get("data", {}).get("qq")) == bot_id:
                    at_me = True
                    break
        
        message_id = getattr(event.message_obj, "message_id", None)
        self._track_pending_message(pending_key, message_id)

        q_type = self.pending[pending_key].get("q_type", "math")
        correct_answer = self.pending[pending_key].get("answer")
        qa_keywords = correct_answer if isinstance(correct_answer, list) else []
        current_question = self.pending[pending_key].get("question", "")
        
        is_attempt = False
        is_correct = False

        allow_plain_answer = self.allow_answer_without_at and not at_me
        can_process_answer = at_me or allow_plain_answer

        if can_process_answer:
            if q_type == "math":
                try:
                    matches = re.findall(r'(\d+)', text)
                    if matches:
                        is_attempt = True
                        if int(matches[-1]) == correct_answer:
                            is_correct = True
                except:
                    pass
            elif q_type == "qa":
                if at_me and text:
                    is_attempt = True
                    if any(keyword in text for keyword in qa_keywords):
                        is_correct = True
                elif allow_plain_answer and text:
                    if any(keyword in text for keyword in qa_keywords):
                        is_attempt = True
                        is_correct = True
            elif q_type == "llm":
                # LLM 开放题需要调用 LLM 评估
                if text:
                    is_attempt = True
                    eval_result = await self._evaluate_llm_answer(
                        question=current_question,
                        keywords=qa_keywords,
                        answer=text,
                    )
                    # 如果 LLM 评估失败且配置为 retry_math，需要切换题目
                    if not eval_result and self.llm_error_behavior == "retry_math":
                        logger.info(f"[QQ Verify] 用户 {uid} LLM 评估未通过，切换为数学题。")
                        # 清除当前 pending 状态，重新生成数学题
                        if pending_key in self.pending:
                            await self._clear_pending_state(event.bot.api, pending_key, gid, uid, "LLM评估失败切换数学题", recall_messages=False)
                        next_timeout = self._get_current_timeout()
                        session_timeout = self.pending.get(pending_key, {}).get("session_timeout_seconds", self.verification_timeout) if pending_key in self.pending else self.verification_timeout
                        await self._start_verification_process(
                            event,
                            uid,
                            gid,
                            timeout_seconds=int(session_timeout) if next_timeout is None else next_timeout,
                            is_new_member=False,
                            force_math=True,
                        )
                        return
                    is_correct = eval_result

        if is_correct:
            logger.info(f"[QQ Verify] 用户 {uid} 在群 {gid} 验证成功。")
            if pending_key in self.pending:
                await self._clear_pending_state(event.bot.api, pending_key, gid, uid, "验证成功", recall_messages=False)

            await self._send_welcome_message(event.bot.api, gid, uid, nickname, self.welcome_message)
        elif is_attempt:
            self.pending[pending_key]["failed_attempts"] += 1
            if self.max_failed_attempts > 0 and self.pending[pending_key]["failed_attempts"] >= self.max_failed_attempts:
                await self._execute_kick(event.bot.api, gid, uid, nickname, "超过最大失败次数")
            else:
                logger.info(f"[QQ Verify] 用户 {uid} 回答错误，生成新问题。")
                force_math = self.switch_to_math_on_failure
                next_timeout = self._get_current_timeout()
                session_timeout = self.pending[pending_key].get("session_timeout_seconds", self.verification_timeout)
                if next_timeout is None:
                    if self.wrong_answer_bypass_behavior == "continue":
                        logger.info(
                            f"[QQ Verify] 用户 {uid} 在群 {gid} 答错后命中免验证时间段，但配置要求继续完成当前验证流程。"
                        )
                        await self._start_verification_process(
                            event,
                            uid,
                            gid,
                            timeout_seconds=int(session_timeout),
                            is_new_member=False,
                            force_math=force_math,
                        )
                    else:
                        logger.info(f"[QQ Verify] 用户 {uid} 在群 {gid} 答错后命中免验证时间段，结束当前验证流程。")
                        if pending_key in self.pending:
                            await self._clear_pending_state(event.bot.api, pending_key, gid, uid, "答错后命中免验证时段", recall_messages=False)
                        await self._send_welcome_message(event.bot.api, gid, uid, nickname, self.bypass_welcome_message)
                else:
                    await self._start_verification_process(event, uid, gid, timeout_seconds=next_timeout, is_new_member=False, force_math=force_math)
            
        else:
            self.pending[pending_key]["unverified_messages"] += 1
            current_unverified = self.pending[pending_key]["unverified_messages"]

            # 自动撤回无关消息
            if self.auto_recall_irrelevant_messages and self.auto_recall_threshold > 0:
                if current_unverified >= self.auto_recall_threshold:
                    if message_id:
                        try:
                            await event.bot.api.call_action("delete_msg", message_id=message_id)
                            logger.debug(f"[QQ Verify] 撤回用户 {uid} 在群 {gid} 的无关消息: {text[:100] if text else '(空消息)'}...")
                        except Exception as e:
                            logger.warning(f"[QQ Verify] 撤回消息 {message_id} 失败: {e}")

            if self.max_unverified_messages > 0 and current_unverified >= self.max_unverified_messages:
                await self._execute_kick(event.bot.api, gid, uid, nickname, "未经验证发送过多无关消息")
            elif self.unverified_reminder_count > 0 and current_unverified == self.unverified_reminder_count:
                if self.unverified_reminder_prompt and self.unverified_reminder_prompt.strip():
                    at_user = f"[CQ:at,qq={uid}]"
                    # 在此处填入保存的 question
                    reminder_msg = self.unverified_reminder_prompt.format(
                        at_user=at_user,
                        member_name=nickname,
                        question=current_question
                    )
                    try:
                        result = await event.bot.api.call_action("send_group_msg", group_id=gid, message=reminder_msg)
                        # 跟踪机器人发送的验证消息ID
                        if result and isinstance(result, dict):
                            bot_msg_id = result.get("message_id")
                            if bot_msg_id:
                                self._track_bot_message(pending_key, bot_msg_id)
                    except Exception: pass

    async def _process_member_decrease(self, event: AstrMessageEvent):
        raw = event.message_obj.raw_message
        uid = str(raw.get("user_id"))
        gid = raw.get("group_id")
        if not gid:
            return

        pending_key = self._create_pending_key(gid, uid)
        if pending_key in self.pending:
            await self._clear_pending_state(event.bot.api, pending_key, gid, uid, "成员离群", recall_messages=True)

    async def _timeout_kick(self, uid: str, gid: int, nickname: str, timeout_seconds: int, expected_expires_at: datetime):
        try:
            wait_before_warning = timeout_seconds - self.kick_countdown_warning_time
            if wait_before_warning > 0:
                await asyncio.sleep(wait_before_warning)

            pending_key = self._create_pending_key(gid, uid)
            if pending_key not in self.pending: return

            bot = self.context.get_platform("aiocqhttp").get_client()
            at_user = f"[CQ:at,qq={uid}]"
            
            if self.kick_countdown_warning_time > 0:
                warning_msg = self.countdown_warning_prompt.format(at_user=at_user, member_name=nickname)
                if warning_msg.strip():
                    try:
                        result = await bot.api.call_action("send_group_msg", group_id=gid, message=warning_msg)
                        # 跟踪机器人发送的验证消息ID
                        if result and isinstance(result, dict):
                            bot_msg_id = result.get("message_id")
                            if bot_msg_id:
                                self._track_bot_message(pending_key, bot_msg_id)
                    except Exception: pass
    
            await asyncio.sleep(self.kick_countdown_warning_time)
    
            if pending_key not in self.pending: return
    
            if self.failure_message and self.failure_message.strip():
                failure_msg = self.failure_message.format(at_user=at_user, member_name=nickname, countdown=self.kick_delay)
                try:
                    result = await bot.api.call_action("send_group_msg", group_id=gid, message=failure_msg)
                    # 跟踪机器人发送的验证消息ID
                    if result and isinstance(result, dict):
                        bot_msg_id = result.get("message_id")
                        if bot_msg_id:
                            self._track_bot_message(pending_key, bot_msg_id)
                except Exception: pass
            
            await asyncio.sleep(self.kick_delay)

            pending_key = self._create_pending_key(gid, uid)
            if pending_key not in self.pending: return
            
            await self._execute_kick(bot.api, gid, uid, nickname, "验证超时", expected_expires_at=expected_expires_at)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[QQ Verify] 踢出流程异常 (用户 {uid}): {e}")
        finally:
            pending_key = self._create_pending_key(gid, uid)
            if pending_key in self.pending:
                self.pending.pop(pending_key, None)