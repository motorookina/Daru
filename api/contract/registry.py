# -*- coding: utf-8 -*-
"""数据族注册表（v1.3）：FIELD_DICT + DATASET + PRIMARY。

字段驱动设计（见 `问题20260911.md` + `数据字典v2_全库.md`）：
  · FIELD_DICT —— 语义名 → 单位（纯词汇表，无 api / col / cat）
  · DATASET    —— 表 → family × asset × historical × prio × entity/time/pit/sem × cols
  · PRIMARY    —— v1 既有字段主表钉死，防 prio 泛化漂移

数据来源：finance_db 全库 53 张表 / 803 语义字段（机器生成，人工维护 TABLES/RENAMES/UNITS）。
单位语义约定："" = 非数值（文本/代码/布尔/日期，沿用 v1 契约输出空串）；"1" = 无量纲数值（新增字段）。
"""
from __future__ import annotations

from enum import StrEnum


class Family(StrEnum):
    DAILY = "daily"    # 交易日粒度：观测日 = 可见日 = 交易日
    PERIOD = "period"  # 报告期/统计期：观测日 = end_date，可见日 = ann_date
    EVENT = "event"    # 一次性事件：观测日 = 事件/生效日，可见日 = 公告/发布日
    STATIC = "static"  # 无时点快照，无历史版本


class Asset(StrEnum):
    STOCK = "stock"        # 个股
    INDEX = "index"        # 指数
    INDUSTRY = "industry"  # 行业与板块指数
    FUT = "fut"            # 期货
    BOND = "bond"          # 债券指数 / 收益率曲线
    RATE = "rate"          # 货币市场回购利率
    MARKET = "market"      # 全市场（跨资产的聚合指标、日历）
    MACRO = "macro"        # 宏观


def ID(cols: str = "", **over) -> dict:
    """cols 书写糖：cols 里列同名直映；over 既可改名 pct_chg="pct_change"，
    也可做列级单位覆盖 amount=("amount", "万元")。"""
    d = {c: c for c in cols.split()}
    for k, v in over.items():
        phys = v[0] if isinstance(v, tuple) else v
        if phys in d:
            del d[phys]
        d[k] = v
    return d


DATASET: dict[str, dict] = {

    # ══════════════ asset = stock ══════════════
    "stock_basic": {  # A股列表（含退市）
        "family": "static", "asset": "stock", "historical": False, "prio": 1,
        "entity": "ts_code", "time": None, "sem": "point",
        "axes": ("symbol", "delist_date"),
        "cols": ID("name area industry fullname enname cnspell market exchange curr_type list_status is_hs list_date"),
    },
    "daily": {  # A股日线行情
        "family": "daily", "asset": "stock", "historical": True, "prio": 1,
        "entity": "ts_code", "time": "trade_date", "sem": "point",
        "cols": ID("open high low close pre_close change pct_chg vol amount"),
    },
    "adj_factor": {  # 复权因子
        "family": "daily", "asset": "stock", "historical": True, "prio": 1,
        "entity": "ts_code", "time": "trade_date", "sem": "point",
        "cols": ID("adj_factor"),
    },
    "daily_basic": {  # 每日指标（估值/股本/市值）
        "family": "daily", "asset": "stock", "historical": True, "prio": 2,
        "entity": "ts_code", "time": "trade_date", "sem": "point",
        "cols": ID(
            "close turnover_rate turnover_rate_f volume_ratio pe pe_ttm pb ps ps_ttm dv_ratio "
            "dv_ttm float_share free_share total_mv circ_mv",
            total_share=("total_share", "万股")
        ),
    },
    "income": {  # 利润表
        "family": "period", "asset": "stock", "historical": True, "prio": 1,
        "entity": "ts_code", "time": "end_date", "pit": ("end_date", "ann_date", 0), "sem": "cumulative",
        "axes": ("f_ann_date",),
        "cols": ID(
            "report_type comp_type end_type basic_eps diluted_eps total_revenue revenue "
            "int_income prem_earned comm_income n_commis_income n_oth_income n_oth_b_income "
            "prem_income out_prem une_prem_reser reins_income n_sec_tb_income n_sec_uw_income "
            "n_asset_mg_income oth_b_income fv_value_chg_gain invest_income ass_invest_income "
            "forex_gain total_cogs oper_cost int_exp comm_exp biz_tax_surchg sell_exp admin_exp "
            "fin_exp assets_impair_loss prem_refund compens_payout reser_insur_liab div_payt "
            "reins_exp oper_exp compens_payout_refu insur_reser_refu reins_cost_refund "
            "other_bus_cost operate_profit non_oper_income non_oper_exp nca_disploss total_profit "
            "income_tax n_income n_income_attr_p minority_gain oth_compr_income t_compr_income "
            "compr_inc_attr_p compr_inc_attr_m_s ebit ebitda insurance_exp undist_profit "
            "distable_profit rd_exp fin_exp_int_exp fin_exp_int_inc transfer_surplus_rese "
            "transfer_housing_imprest transfer_oth adj_lossgain withdra_legal_surplus "
            "withdra_legal_pubfund withdra_biz_devfund withdra_rese_fund withdra_oth_ersu "
            "workers_welfare distr_profit_shrhder prfshare_payable_dvd comshare_payable_dvd "
            "capit_comstock_div update_flag net_after_nr_lp_correct credit_impa_loss "
            "net_expo_hedging_benefits oth_impair_loss_assets total_opcost amodcost_fin_assets "
            "oth_income asset_disp_income continued_net_profit end_net_profit"
        ),
    },
    "balancesheet": {  # 资产负债表
        "family": "period", "asset": "stock", "historical": True, "prio": 1,
        "entity": "ts_code", "time": "end_date", "pit": ("end_date", "ann_date", 0), "sem": "point",
        "axes": ("f_ann_date",),
        "cols": ID(
            "report_type comp_type end_type total_share cap_rese undistr_porfit surplus_rese "
            "special_rese money_cap trad_asset notes_receiv accounts_receiv oth_receiv prepayment "
            "div_receiv int_receiv inventories amor_exp nca_within_1y sett_rsrv "
            "loanto_oth_bank_fi premium_receiv reinsur_receiv reinsur_res_receiv pur_resale_fa "
            "oth_cur_assets total_cur_assets fa_avail_for_sale htm_invest lt_eqt_invest "
            "invest_real_estate time_deposits oth_assets lt_rec fix_assets cip const_materials "
            "fixed_assets_disp produc_bio_assets oil_and_gas_assets intan_assets r_and_d goodwill "
            "lt_amor_exp defer_tax_assets decr_in_disbur oth_nca total_nca cash_reser_cb "
            "depos_in_oth_bfi prec_metals deriv_assets rr_reins_une_prem rr_reins_outstd_cla "
            "rr_reins_lins_liab rr_reins_lthins_liab refund_depos ph_pledge_loans "
            "refund_cap_depos indep_acct_assets client_depos client_prov transac_seat_fee "
            "invest_as_receiv total_assets lt_borr st_borr cb_borr depos_ib_deposits "
            "loan_oth_bank trading_fl notes_payable acct_payable adv_receipts sold_for_repur_fa "
            "comm_payable payroll_payable taxes_payable int_payable div_payable oth_payable "
            "acc_exp deferred_inc st_bonds_payable payable_to_reinsurer rsrv_insur_cont "
            "acting_trading_sec acting_uw_sec non_cur_liab_due_1y oth_cur_liab total_cur_liab "
            "bond_payable lt_payable specific_payables estimated_liab defer_tax_liab "
            "defer_inc_non_cur_liab oth_ncl total_ncl depos_oth_bfi deriv_liab depos "
            "agency_bus_liab oth_liab prem_receiv_adva depos_received ph_invest reser_une_prem "
            "reser_outstd_claims reser_lins_liab reser_lthins_liab indept_acc_liab pledge_borr "
            "indem_payable policy_div_payable total_liab treasury_share ordin_risk_reser "
            "forex_differ invest_loss_unconf minority_int total_hldr_eqy_exc_min_int "
            "total_hldr_eqy_inc_min_int total_liab_hldr_eqy lt_payroll_payable oth_comp_income "
            "oth_eqt_tools oth_eqt_tools_p_shr lending_funds acc_receivable st_fin_payable "
            "payables hfs_assets hfs_sales cost_fin_assets fair_value_fin_assets cip_total "
            "oth_pay_total long_pay_total debt_invest oth_debt_invest oth_eq_invest "
            "oth_illiq_fin_assets oth_eq_ppbond receiv_financing use_right_assets lease_liab "
            "contract_assets contract_liab accounts_receiv_bill accounts_pay oth_rcv_total "
            "fix_assets_total update_flag"
        ),
    },
    "cashflow": {  # 现金流量表
        "family": "period", "asset": "stock", "historical": True, "prio": 1,
        "entity": "ts_code", "time": "end_date", "pit": ("end_date", "ann_date", 0), "sem": "cumulative",
        "axes": ("f_ann_date",),
        "cols": ID(
            "comp_type report_type end_type net_profit finan_exp c_fr_sale_sg recp_tax_rends "
            "n_depos_incr_fi n_incr_loans_cb n_inc_borr_oth_fi prem_fr_orig_contr "
            "n_incr_insured_dep n_reinsur_prem n_incr_disp_tfa ifc_cash_incr n_incr_disp_faas "
            "n_incr_loans_oth_bank n_cap_incr_repur c_fr_oth_operate_a c_inf_fr_operate_a "
            "c_paid_goods_s c_paid_to_for_empl c_paid_for_taxes n_incr_clt_loan_adv "
            "n_incr_dep_cbob c_pay_claims_orig_inco pay_handling_chrg pay_comm_insur_plcy "
            "oth_cash_pay_oper_act st_cash_out_act n_cashflow_act oth_recp_ral_inv_act "
            "c_disp_withdrwl_invest c_recp_return_invest n_recp_disp_fiolta n_recp_disp_sobu "
            "stot_inflows_inv_act c_pay_acq_const_fiolta c_paid_invest n_disp_subs_oth_biz "
            "oth_pay_ral_inv_act n_incr_pledge_loan stot_out_inv_act n_cashflow_inv_act "
            "c_recp_borrow proc_issue_bonds oth_cash_recp_ral_fnc_act stot_cash_in_fnc_act "
            "free_cashflow c_prepay_amt_borr c_pay_dist_dpcp_int_exp incl_dvd_profit_paid_sc_ms "
            "oth_cashpay_ral_fnc_act stot_cashout_fnc_act n_cash_flows_fnc_act eff_fx_flu_cash "
            "n_incr_cash_cash_equ c_cash_equ_beg_period c_cash_equ_end_period c_recp_cap_contrib "
            "incl_cash_rec_saims uncon_invest_loss prov_depr_assets depr_fa_coga_dpba "
            "amort_intang_assets lt_amort_deferred_exp decr_deferred_exp incr_acc_exp "
            "loss_disp_fiolta loss_scr_fa loss_fv_chg invest_loss decr_def_inc_tax_assets "
            "incr_def_inc_tax_liab decr_inventories decr_oper_payable incr_oper_payable others "
            "im_net_cashflow_oper_act conv_debt_into_cap conv_copbonds_due_within_1y "
            "fa_fnc_leases im_n_incr_cash_equ net_dism_capital_add net_cash_rece_sec "
            "credit_impa_loss use_right_asset_dep oth_loss_asset end_bal_cash beg_bal_cash "
            "end_bal_cash_equ beg_bal_cash_equ update_flag"
        ),
    },
    "fina_indicator": {  # 财务指标
        "family": "period", "asset": "stock", "historical": True, "prio": 2,
        "entity": "ts_code", "time": "end_date", "pit": ("end_date", "ann_date", 0), "sem": "point",
        "cols": ID(
            "eps dt_eps total_revenue_ps revenue_ps capital_rese_ps surplus_rese_ps "
            "undist_profit_ps extra_item profit_dedt gross_margin current_ratio quick_ratio "
            "cash_ratio ar_turn ca_turn fa_turn assets_turn op_income ebit ebitda fcff fcfe "
            "current_exint noncurrent_exint interestdebt netdebt tangible_asset working_capital "
            "networking_capital invest_capital retained_earnings diluted2_eps bps ocfps "
            "retainedps cfps ebit_ps fcff_ps fcfe_ps netprofit_margin grossprofit_margin "
            "cogs_of_sales expense_of_sales profit_to_gr saleexp_to_gr adminexp_of_gr "
            "finaexp_of_gr impai_ttm gc_of_gr op_of_gr ebit_of_gr roe roe_waa roe_dt roa npta "
            "roic roe_yearly roa2_yearly debt_to_assets assets_to_eqt dp_assets_to_eqt "
            "ca_to_assets nca_to_assets tbassets_to_totalassets int_to_talcap eqt_to_talcapital "
            "currentdebt_to_debt longdeb_to_debt ocf_to_shortdebt debt_to_eqt eqt_to_debt "
            "eqt_to_interestdebt tangibleasset_to_debt tangasset_to_intdebt "
            "tangibleasset_to_netdebt ocf_to_debt turn_days roa_yearly roa_dp fixed_assets "
            "profit_to_op q_saleexp_to_gr q_gc_to_gr q_roe q_dt_roe q_npta q_ocf_to_sales "
            "basic_eps_yoy dt_eps_yoy cfps_yoy op_yoy ebt_yoy netprofit_yoy dt_netprofit_yoy "
            "ocf_yoy roe_yoy bps_yoy assets_yoy eqt_yoy tr_yoy or_yoy q_sales_yoy q_op_qoq "
            "equity_yoy update_flag"
        ),
    },
    "express": {  # 业绩快报
        "family": "period", "asset": "stock", "historical": True, "prio": 2,
        "entity": "ts_code", "time": "end_date", "pit": ("end_date", "ann_date", 0), "sem": "cumulative",
        "cols": ID(
            "revenue operate_profit total_profit n_income total_assets total_hldr_eqy_exc_min_int "
            "diluted_eps diluted_roe yoy_net_profit bps perf_summary update_flag"
        ),
    },
    "forecast": {  # 业绩预告
        "family": "period", "asset": "stock", "historical": True, "prio": 3,
        "entity": "ts_code", "time": "end_date", "pit": ("end_date", "ann_date", 0), "sem": "point",
        "axes": ("first_ann_date",),
        "cols": ID(
            "type p_change_min p_change_max net_profit_min net_profit_max last_parent_net summary "
            "change_reason update_flag"
        ),
    },
    "fina_audit": {  # 财务审计意见
        "family": "period", "asset": "stock", "historical": True, "prio": 4,
        "entity": "ts_code", "time": "end_date", "pit": ("end_date", "ann_date", 0), "sem": "point",
        "axes": ("created_at", "updated_at"),
        "cols": ID("audit_result audit_fees audit_agency audit_sign"),
    },
    "stk_holdernumber": {  # 股东户数
        "family": "period", "asset": "stock", "historical": True, "prio": 4,
        "entity": "ts_code", "time": "end_date", "pit": ("end_date", "ann_date", 0), "sem": "point",
        "cols": ID("holder_num"),
    },
    "stk_rewards": {  # 管理层薪酬与持股
        "family": "period", "asset": "stock", "historical": True, "prio": 4,
        "entity": "ts_code", "time": "end_date", "pit": ("end_date", "ann_date", 0), "sem": "point",
        "cols": ID("name title reward hold_vol"),
    },
    "cyq_perf": {  # 每日筹码分布
        "family": "daily", "asset": "stock", "historical": True, "prio": 3,
        "entity": "ts_code", "time": "trade_date", "sem": "point",
        "cols": ID("his_low his_high cost_5pct cost_15pct cost_50pct cost_85pct cost_95pct weight_avg winner_rate"),
    },
    "moneyflow": {  # 个股资金流向
        "family": "daily", "asset": "stock", "historical": True, "prio": 3,
        "entity": "ts_code", "time": "trade_date", "sem": "point",
        "cols": ID(
            "buy_sm_vol buy_sm_amount sell_sm_vol sell_sm_amount buy_md_vol buy_md_amount "
            "sell_md_vol sell_md_amount buy_lg_vol buy_lg_amount sell_lg_vol sell_lg_amount "
            "buy_elg_vol buy_elg_amount sell_elg_vol sell_elg_amount net_mf_vol net_mf_amount"
        ),
    },
    "moneyflow_dc": {  # 个股资金流向（东财）
        "family": "daily", "asset": "stock", "historical": True, "prio": 3,
        "entity": "ts_code", "time": "trade_date", "sem": "point",
        "cols": ID(
            "name close net_amount net_amount_rate buy_elg_amount buy_elg_amount_rate "
            "buy_lg_amount buy_lg_amount_rate buy_md_amount buy_md_amount_rate buy_sm_amount "
            "buy_sm_amount_rate",
            pct_chg="pct_change"
        ),
    },
    "margin_detail": {  # 融资融券明细
        "family": "daily", "asset": "stock", "historical": True, "prio": 3,
        "entity": "ts_code", "time": "trade_date", "sem": "point",
        "cols": ID("name rzye rqye rzmre rqyl rzche rqchl rqmcl rzrqye"),
    },
    "hk_hold": {  # 陆股通持股
        "family": "daily", "asset": "stock", "historical": True, "prio": 4,
        "entity": "ts_code", "time": "trade_date", "sem": "point",
        "axes": ("code",),
        "cols": ID("name ratio exchange", hold_vol="vol"),
    },
    "hsgt_top10": {  # 沪深股通十大成交股
        "family": "daily", "asset": "stock", "historical": True, "prio": 4,
        "entity": "ts_code", "time": "trade_date", "sem": "point",
        "cols": ID("name close change rank market_type net_amount buy sell", amount=("amount", "万元")),
    },
    "top_list": {  # 龙虎榜每日明细
        "family": "daily", "asset": "stock", "historical": True, "prio": 4,
        "entity": "ts_code", "time": "trade_date", "sem": "point",
        "cols": ID(
            "name close turnover_rate l_sell l_buy l_amount net_rate amount_rate float_values "
            "reason",
            pct_chg="pct_change",
            amount=("amount", "元"),
            net_amount=("net_amount", "元")
        ),
    },
    "top_inst": {  # 龙虎榜机构席位
        "family": "daily", "asset": "stock", "historical": True, "prio": 4,
        "entity": "ts_code", "time": "trade_date", "sem": "point",
        "cols": ID("exalter side buy_rate sell_rate net_buy reason", buy=("buy", "元"), sell=("sell", "元")),
    },
    "namechange": {  # 股票曾用名
        "family": "event", "asset": "stock", "historical": True, "prio": 4,
        "entity": "ts_code", "time": "start_date", "pit": ("start_date", "ann_date", 0), "sem": "point",
        "axes": ("end_date",),
        "cols": ID("name change_reason"),
    },
    "report_rc": {  # 券商盈利预测
        "family": "event", "asset": "stock", "historical": True, "prio": 4,
        "entity": "ts_code", "time": "report_date", "pit": ("report_date", "report_date", 0), "sem": "point",
        "axes": ("id", "create_time"),
        "cols": ID(
            "name report_title report_type classify org_name author_name quarter op_rt op_pr tp "
            "np eps pe rd roe ev_ebitda rating max_price min_price imp_dg"
        ),
    },

    # ══════════════ asset = index ══════════════
    "index_basic": {  # 指数基本信息
        "family": "static", "asset": "index", "historical": False, "prio": 1,
        "entity": "ts_code", "time": None, "sem": "point",
        "axes": ("base_date", "list_date"),
        "cols": ID("name market publisher category base_point"),
    },
    "index_daily": {  # 指数日线行情
        "family": "daily", "asset": "index", "historical": True, "prio": 1,
        "entity": "ts_code", "time": "trade_date", "sem": "point",
        "cols": ID(
            "pct_chg vol amount",
            close=("close", "点"),
            open=("open", "点"),
            high=("high", "点"),
            low=("low", "点"),
            pre_close=("pre_close", "点"),
            change=("change", "点")
        ),
    },
    "index_dailybasic": {  # 指数每日指标
        "family": "daily", "asset": "index", "historical": True, "prio": 2,
        "entity": "ts_code", "time": "trade_date", "sem": "point",
        "cols": ID(
            "total_mv float_share free_share turnover_rate turnover_rate_f pe pe_ttm pb",
            circ_mv="float_mv",
            total_share=("total_share", "万股")
        ),
    },
    "idx_factor_pro": {  # 指数技术面因子（专业版）
        "family": "daily", "asset": "index", "historical": True, "prio": 3,
        "entity": "ts_code", "time": "trade_date", "sem": "point",
        "cols": ID(
            "vol amount asi_bfq asit_bfq atr_bfq bbi_bfq bias1_bfq bias2_bfq bias3_bfq "
            "boll_lower_bfq boll_mid_bfq boll_upper_bfq brar_ar_bfq brar_br_bfq cci_bfq cr_bfq "
            "dfma_dif_bfq dfma_difma_bfq dmi_adx_bfq dmi_adxr_bfq dmi_mdi_bfq dmi_pdi_bfq "
            "downdays updays dpo_bfq madpo_bfq ema_bfq_10 ema_bfq_20 ema_bfq_250 ema_bfq_30 "
            "ema_bfq_5 ema_bfq_60 ema_bfq_90 emv_bfq maemv_bfq expma_12_bfq expma_50_bfq kdj_bfq "
            "kdj_d_bfq kdj_k_bfq ktn_down_bfq ktn_mid_bfq ktn_upper_bfq lowdays topdays ma_bfq_10 "
            "ma_bfq_20 ma_bfq_250 ma_bfq_30 ma_bfq_5 ma_bfq_60 ma_bfq_90 macd_bfq macd_dea_bfq "
            "macd_dif_bfq mass_bfq ma_mass_bfq mfi_bfq mtm_bfq mtmma_bfq obv_bfq psy_bfq "
            "psyma_bfq roc_bfq maroc_bfq rsi_bfq_12 rsi_bfq_24 rsi_bfq_6 taq_down_bfq taq_mid_bfq "
            "taq_up_bfq trix_bfq trma_bfq vr_bfq wr_bfq wr1_bfq xsii_td1_bfq xsii_td2_bfq "
            "xsii_td3_bfq xsii_td4_bfq",
            open=("open", "点"),
            high=("high", "点"),
            low=("low", "点"),
            close=("close", "点"),
            pre_close=("pre_close", "点"),
            change=("change", "点"),
            pct_chg="pct_change"
        ),
    },
    "index_global": {  # 国际指数行情
        "family": "daily", "asset": "index", "historical": True, "prio": 3,
        "entity": "ts_code", "time": "trade_date", "sem": "point",
        "cols": ID(
            "pct_chg swing vol",
            open=("open", "点"),
            close=("close", "点"),
            high=("high", "点"),
            low=("low", "点"),
            pre_close=("pre_close", "点"),
            change=("change", "点")
        ),
    },
    "index_weight": {  # 指数成分与权重
        "family": "daily", "asset": "index", "historical": True, "prio": 3,
        "entity": "index_code", "time": "trade_date", "sem": "point",
        "axes": ("con_code",),
        "cols": ID("weight"),
    },
    "lx_index_fundamental": {  # 乐咕指数估值
        "family": "daily", "asset": "index", "historical": True, "prio": 4,
        "entity": "stock_code", "time": "date", "sem": "point",
        "cols": ID("pe_ttm pb dyr"),
    },
    "lx_index_tr": {  # 乐咕指数行情
        "family": "daily", "asset": "index", "historical": True, "prio": 4,
        "entity": "stock_code", "time": "date", "sem": "point",
        "cols": ID("amount", close=("close", "点"), change=("change", "点"), vol="volume"),
    },
    "stock_index_pe_lg": {  # 乐咕指数PE
        "family": "daily", "asset": "index", "historical": True, "prio": 4,
        "entity": "symbol", "time": "date", "sem": "point",
        "cols": ID("index_value pe_lyr_ew pe_lyr pe_lyr_median pe_ttm_ew pe_ttm pe_ttm_median"),
    },
    "stock_index_pb_lg": {  # 乐咕指数PB
        "family": "daily", "asset": "index", "historical": True, "prio": 4,
        "entity": "symbol", "time": "date", "sem": "point",
        "cols": ID("index_value pb pb_ew pb_median"),
    },

    # ══════════════ asset = industry ══════════════
    "sw_daily": {  # 申万行业日线
        "family": "daily", "asset": "industry", "historical": True, "prio": 2,
        "entity": "ts_code", "time": "trade_date", "sem": "point",
        "cols": ID(
            "name vol amount pe pb total_mv",
            open=("open", "点"),
            low=("low", "点"),
            high=("high", "点"),
            close=("close", "点"),
            change=("change", "点"),
            pct_chg="pct_change",
            circ_mv="float_mv"
        ),
    },
    "index_hist_sw": {  # 申万行业指数历史
        "family": "daily", "asset": "industry", "historical": True, "prio": 3,
        "entity": "symbol", "time": "date", "sem": "point",
        "cols": ID("amount", close=("close", "点"), open=("open", "点"), high=("high", "点"), low=("low", "点"), vol="volume"),
    },
    "ths_daily": {  # 同花顺板块指数
        "family": "daily", "asset": "industry", "historical": True, "prio": 3,
        "entity": "ts_code", "time": "trade_date", "sem": "point",
        "cols": ID(
            "avg_price vol turnover_rate",
            open=("open", "点"),
            high=("high", "点"),
            low=("low", "点"),
            close=("close", "点"),
            pre_close=("pre_close", "点"),
            change=("change", "点"),
            pct_chg="pct_change"
        ),
    },
    "lx_industry_fundamental": {  # 乐咕行业估值
        "family": "daily", "asset": "industry", "historical": True, "prio": 4,
        "entity": "industry_code", "time": "date", "sem": "point",
        "cols": ID("pe_ttm pb dyr"),
    },

    # ══════════════ asset = fut ══════════════
    "fut_basic": {  # 期货合约信息
        "family": "static", "asset": "fut", "historical": False, "prio": 1,
        "entity": "ts_code", "time": None, "sem": "point",
        "axes": ("symbol", "exchange", "fut_code", "list_date", "delist_date", "last_ddate"),
        "cols": ID("name multiplier trade_unit per_unit quote_unit quote_unit_desc d_mode_desc d_month"),
    },
    "fut_daily": {  # 期货日线行情
        "family": "daily", "asset": "fut", "historical": True, "prio": 1,
        "entity": "ts_code", "time": "trade_date", "sem": "point",
        "cols": ID(
            "pre_close pre_settle open high low close settle change1 change2 vol oi oi_chg",
            amount=("amount", "万元")
        ),
    },
    "futures_main_sina": {  # 新浪期货主力连续
        "family": "daily", "asset": "fut", "historical": True, "prio": 3,
        "entity": "symbol", "time": "date", "sem": "point",
        "cols": ID("open high low close settle", vol="volume", oi="open_interest"),
    },

    # ══════════════ asset = bond ══════════════
    "bond_china_yield": {  # 中债国债收益率曲线
        "family": "daily", "asset": "bond", "historical": True, "prio": 3,
        "entity": "curve_name", "time": "date", "sem": "point",
        "cols": ID("m3 m6 y1 y3 y5 y7 y10 y30"),
    },
    "bond_new_composite_index_cbond": {  # 中债新综合指数
        "family": "daily", "asset": "bond", "historical": True, "prio": 4,
        "entity": "indicator", "time": "date", "sem": "point",
        "axes": ("period",),
        "cols": ID(value=("value", "点")),
    },

    # ══════════════ asset = rate ══════════════
    "repo_rate_hist": {  # 银行间质押式回购利率
        "family": "daily", "asset": "rate", "historical": True, "prio": 3,
        "entity": None, "time": "date", "sem": "point",
        "cols": ID("fr001 fr007 fr014 fdr001 fdr007 fdr014"),
    },

    # ══════════════ asset = market ══════════════
    "trade_cal": {  # 交易日历（v1 契约：historical=True，有完整日历历史，非「当前快照」）
        "family": "static", "asset": "market", "historical": True, "prio": 1,
        "entity": "exchange", "time": None, "sem": "point",
        "axes": ("cal_date", "pretrade_date"),
        "cols": ID("is_open"),
    },
    "stock_market_pe_lg": {  # 乐咕全市场PE
        "family": "daily", "asset": "market", "historical": True, "prio": 3,
        "entity": "symbol", "time": "date", "sem": "point",
        "cols": ID("index_value pe"),
    },
    "stock_market_pb_lg": {  # 乐咕全市场PB
        "family": "daily", "asset": "market", "historical": True, "prio": 3,
        "entity": "symbol", "time": "date", "sem": "point",
        "cols": ID("index_value pb pb_ew pb_median"),
    },

    # ══════════════ asset = macro ══════════════
    "cn_cpi": {  # 居民消费价格指数
        "family": "period", "asset": "macro", "historical": True, "prio": 3,
        "entity": None, "time": "month", "pit": ("month", "month", 15), "sem": "cumulative",
        "cols": ID("nt_val nt_yoy nt_mom nt_accu town_val town_yoy town_mom town_accu cnt_val cnt_yoy cnt_mom cnt_accu"),
    },
    "cn_ppi": {  # 工业生产者出厂价格指数
        "family": "period", "asset": "macro", "historical": True, "prio": 3,
        "entity": None, "time": "month", "pit": ("month", "month", 15), "sem": "cumulative",
        "cols": ID(
            "ppi_yoy ppi_mp_yoy ppi_mp_qm_yoy ppi_mp_rm_yoy ppi_mp_p_yoy ppi_cg_yoy ppi_cg_f_yoy "
            "ppi_cg_c_yoy ppi_cg_adu_yoy ppi_cg_dcg_yoy ppi_mom ppi_mp_mom ppi_mp_qm_mom "
            "ppi_mp_rm_mom ppi_mp_p_mom ppi_cg_mom ppi_cg_f_mom ppi_cg_c_mom ppi_cg_adu_mom "
            "ppi_cg_dcg_mom ppi_accu ppi_mp_accu ppi_mp_qm_accu ppi_mp_rm_accu ppi_mp_p_accu "
            "ppi_cg_accu ppi_cg_f_accu ppi_cg_c_accu ppi_cg_adu_accu ppi_cg_dcg_accu"
        ),
    },
    "cn_pmi": {  # 采购经理人指数
        "family": "period", "asset": "macro", "historical": True, "prio": 3,
        "entity": None, "time": "month", "pit": ("month", "month", 1), "sem": "point",
        "axes": ("created_at", "updated_at"),
        "cols": ID(
            "pmi010000 pmi010100 pmi010200 pmi010300 pmi010400 pmi010401 pmi010402 pmi010403 "
            "pmi010500 pmi010501 pmi010502 pmi010503 pmi010600 pmi010601 pmi010602 pmi010603 "
            "pmi010700 pmi010701 pmi010702 pmi010703 pmi010800 pmi010801 pmi010802 pmi010803 "
            "pmi010900 pmi011000 pmi011100 pmi011200 pmi011300 pmi011400 pmi011500 pmi011600 "
            "pmi011700 pmi011800 pmi011900 pmi012000 pmi020100 pmi020101 pmi020102 pmi020200 "
            "pmi020201 pmi020202 pmi020300 pmi020301 pmi020302 pmi020400 pmi020401 pmi020402 "
            "pmi020500 pmi020501 pmi020502 pmi020600 pmi020601 pmi020602 pmi020700 pmi020800 "
            "pmi020900 pmi021000 pmi030000"
        ),
    },
    "cn_gdp": {  # 国内生产总值
        "family": "period", "asset": "macro", "historical": True, "prio": 3,
        "entity": None, "time": "quarter", "pit": ("quarter", "quarter", 20), "sem": "cumulative",
        "cols": ID("gdp gdp_yoy pi pi_yoy si si_yoy ti ti_yoy"),
    },
    "sf_month": {  # 社会融资规模增量
        "family": "period", "asset": "macro", "historical": True, "prio": 3,
        "entity": None, "time": "month", "pit": ("month", "month", 15), "sem": "cumulative",
        "cols": ID("inc_month inc_cumval stk_endval"),
    },
    "macro_bank_china_interest_rate": {  # 央行基准利率调整
        "family": "event", "asset": "macro", "historical": True, "prio": 3,
        "entity": "name", "time": "date", "sem": "point",
        "cols": ID("value forecast prev"),
    },
    "macro_china_reserve_requirement_ratio": {  # 存款准备金率调整
        "family": "event", "asset": "macro", "historical": True, "prio": 3,
        "entity": None, "time": "effect_date", "sem": "point",
        "axes": ("ann_date",),
        "cols": ID("big_before big_after big_change sml_before sml_after sml_change next_sh next_sz note"),
    },
}


FIELD_DICT: dict[str, dict] = {}


def U(unit, names: str) -> None:
    """批量登记同一单位的语义字段。"""
    for n in names.split():
        FIELD_DICT[n] = {"unit": unit}


# ── 单位：元 ──
U("元", """open high low close pre_close change basic_eps diluted_eps total_revenue revenue int_income
    prem_earned comm_income n_commis_income n_oth_income n_oth_b_income prem_income out_prem
    une_prem_reser reins_income n_sec_tb_income n_sec_uw_income n_asset_mg_income oth_b_income
    fv_value_chg_gain invest_income ass_invest_income forex_gain total_cogs oper_cost int_exp
    comm_exp biz_tax_surchg sell_exp admin_exp fin_exp assets_impair_loss prem_refund compens_payout
    reser_insur_liab div_payt reins_exp oper_exp compens_payout_refu insur_reser_refu
    reins_cost_refund other_bus_cost operate_profit non_oper_income non_oper_exp nca_disploss
    total_profit income_tax n_income n_income_attr_p minority_gain oth_compr_income t_compr_income
    compr_inc_attr_p compr_inc_attr_m_s ebit ebitda insurance_exp undist_profit distable_profit
    rd_exp fin_exp_int_exp fin_exp_int_inc transfer_surplus_rese transfer_housing_imprest
    transfer_oth adj_lossgain withdra_legal_surplus withdra_legal_pubfund withdra_biz_devfund
    withdra_rese_fund withdra_oth_ersu workers_welfare distr_profit_shrhder prfshare_payable_dvd
    comshare_payable_dvd capit_comstock_div net_after_nr_lp_correct credit_impa_loss
    net_expo_hedging_benefits oth_impair_loss_assets total_opcost amodcost_fin_assets oth_income
    asset_disp_income continued_net_profit end_net_profit cap_rese undistr_porfit surplus_rese
    special_rese money_cap trad_asset notes_receiv accounts_receiv oth_receiv prepayment div_receiv
    int_receiv inventories amor_exp nca_within_1y sett_rsrv loanto_oth_bank_fi premium_receiv
    reinsur_receiv reinsur_res_receiv pur_resale_fa oth_cur_assets total_cur_assets
    fa_avail_for_sale htm_invest lt_eqt_invest invest_real_estate time_deposits oth_assets lt_rec
    fix_assets cip const_materials fixed_assets_disp produc_bio_assets oil_and_gas_assets
    intan_assets r_and_d goodwill lt_amor_exp defer_tax_assets decr_in_disbur oth_nca total_nca
    cash_reser_cb depos_in_oth_bfi prec_metals deriv_assets rr_reins_une_prem rr_reins_outstd_cla
    rr_reins_lins_liab rr_reins_lthins_liab refund_depos ph_pledge_loans refund_cap_depos
    indep_acct_assets client_depos client_prov transac_seat_fee invest_as_receiv total_assets
    lt_borr st_borr cb_borr depos_ib_deposits loan_oth_bank trading_fl notes_payable acct_payable
    adv_receipts sold_for_repur_fa comm_payable payroll_payable taxes_payable int_payable
    div_payable oth_payable acc_exp deferred_inc st_bonds_payable payable_to_reinsurer
    rsrv_insur_cont acting_trading_sec acting_uw_sec non_cur_liab_due_1y oth_cur_liab total_cur_liab
    bond_payable lt_payable specific_payables estimated_liab defer_tax_liab defer_inc_non_cur_liab
    oth_ncl total_ncl depos_oth_bfi deriv_liab depos agency_bus_liab oth_liab prem_receiv_adva
    depos_received ph_invest reser_une_prem reser_outstd_claims reser_lins_liab reser_lthins_liab
    indept_acc_liab pledge_borr indem_payable policy_div_payable total_liab treasury_share
    ordin_risk_reser forex_differ invest_loss_unconf minority_int total_hldr_eqy_exc_min_int
    total_hldr_eqy_inc_min_int total_liab_hldr_eqy lt_payroll_payable oth_comp_income oth_eqt_tools
    oth_eqt_tools_p_shr lending_funds acc_receivable st_fin_payable payables hfs_assets hfs_sales
    cost_fin_assets fair_value_fin_assets cip_total oth_pay_total long_pay_total debt_invest
    oth_debt_invest oth_eq_invest oth_illiq_fin_assets oth_eq_ppbond receiv_financing
    use_right_assets lease_liab contract_assets contract_liab accounts_receiv_bill accounts_pay
    oth_rcv_total fix_assets_total net_profit finan_exp c_fr_sale_sg recp_tax_rends n_depos_incr_fi
    n_incr_loans_cb n_inc_borr_oth_fi prem_fr_orig_contr n_incr_insured_dep n_reinsur_prem
    n_incr_disp_tfa ifc_cash_incr n_incr_disp_faas n_incr_loans_oth_bank n_cap_incr_repur
    c_fr_oth_operate_a c_inf_fr_operate_a c_paid_goods_s c_paid_to_for_empl c_paid_for_taxes
    n_incr_clt_loan_adv n_incr_dep_cbob c_pay_claims_orig_inco pay_handling_chrg pay_comm_insur_plcy
    oth_cash_pay_oper_act st_cash_out_act n_cashflow_act oth_recp_ral_inv_act c_disp_withdrwl_invest
    c_recp_return_invest n_recp_disp_fiolta n_recp_disp_sobu stot_inflows_inv_act
    c_pay_acq_const_fiolta c_paid_invest n_disp_subs_oth_biz oth_pay_ral_inv_act n_incr_pledge_loan
    stot_out_inv_act n_cashflow_inv_act c_recp_borrow proc_issue_bonds oth_cash_recp_ral_fnc_act
    stot_cash_in_fnc_act free_cashflow c_prepay_amt_borr c_pay_dist_dpcp_int_exp
    incl_dvd_profit_paid_sc_ms oth_cashpay_ral_fnc_act stot_cashout_fnc_act n_cash_flows_fnc_act
    eff_fx_flu_cash n_incr_cash_cash_equ c_cash_equ_beg_period c_cash_equ_end_period
    c_recp_cap_contrib incl_cash_rec_saims uncon_invest_loss prov_depr_assets depr_fa_coga_dpba
    amort_intang_assets lt_amort_deferred_exp decr_deferred_exp incr_acc_exp loss_disp_fiolta
    loss_scr_fa loss_fv_chg invest_loss decr_def_inc_tax_assets incr_def_inc_tax_liab
    decr_inventories decr_oper_payable incr_oper_payable others im_net_cashflow_oper_act
    conv_debt_into_cap conv_copbonds_due_within_1y fa_fnc_leases im_n_incr_cash_equ
    net_dism_capital_add net_cash_rece_sec use_right_asset_dep oth_loss_asset end_bal_cash
    beg_bal_cash end_bal_cash_equ beg_bal_cash_equ pre_settle settle change1 change2 eps dt_eps
    total_revenue_ps revenue_ps capital_rese_ps surplus_rese_ps undist_profit_ps extra_item
    profit_dedt op_income fcff fcfe current_exint noncurrent_exint interestdebt netdebt
    tangible_asset working_capital networking_capital invest_capital retained_earnings diluted2_eps
    bps ocfps retainedps cfps ebit_ps fcff_ps fcfe_ps roa_dp fixed_assets his_low his_high cost_5pct
    cost_15pct cost_50pct cost_85pct cost_95pct weight_avg rzye rqye rzmre rzche rzrqye audit_fees
    reward l_sell l_buy l_amount float_values net_buy max_price min_price
    """)

# ── 单位：万元 ──
U("万元", """total_mv circ_mv net_profit_min net_profit_max last_parent_net buy_sm_amount sell_sm_amount
    buy_md_amount sell_md_amount buy_lg_amount sell_lg_amount buy_elg_amount sell_elg_amount
    net_mf_amount net_amount buy sell
    """)

# ── 单位：亿元 ──
U("亿元", """gdp pi si ti inc_month inc_cumval stk_endval op_rt op_pr tp np rd
    """)

# ── 单位：千元 ──
U("千元", """amount
    """)

# ── 单位：万股 ──
U("万股", """float_share free_share
    """)

# ── 单位：股 ──
U("股", """total_share rqyl rqchl rqmcl hold_vol
    """)

# ── 单位：手 ──
U("手", """vol oi oi_chg buy_sm_vol sell_sm_vol buy_md_vol sell_md_vol buy_lg_vol sell_lg_vol buy_elg_vol
    sell_elg_vol net_mf_vol
    """)

# ── 单位：户 ──
U("户", """holder_num
    """)

# ── 单位：倍 ──
U("倍", """adj_factor multiplier volume_ratio pe pe_ttm pb ps ps_ttm current_ratio quick_ratio cash_ratio
    ar_turn ca_turn fa_turn assets_turn assets_to_eqt ocf_to_shortdebt debt_to_eqt eqt_to_debt
    tangibleasset_to_debt tangasset_to_intdebt tangibleasset_to_netdebt ocf_to_debt pb_ew pb_median
    ev_ebitda pe_lyr_ew pe_lyr pe_lyr_median pe_ttm_ew pe_ttm_median
    """)

# ── 单位：% ──
U("%", """pct_chg turnover_rate turnover_rate_f dv_ratio dv_ttm gross_margin netprofit_margin
    grossprofit_margin cogs_of_sales expense_of_sales profit_to_gr saleexp_to_gr adminexp_of_gr
    finaexp_of_gr impai_ttm gc_of_gr op_of_gr ebit_of_gr roe roe_waa roe_dt roa npta roic roe_yearly
    roa2_yearly debt_to_assets dp_assets_to_eqt ca_to_assets nca_to_assets tbassets_to_totalassets
    int_to_talcap eqt_to_talcapital currentdebt_to_debt longdeb_to_debt eqt_to_interestdebt
    roa_yearly profit_to_op q_saleexp_to_gr q_gc_to_gr q_roe q_dt_roe q_npta q_ocf_to_sales
    basic_eps_yoy dt_eps_yoy cfps_yoy op_yoy ebt_yoy netprofit_yoy dt_netprofit_yoy ocf_yoy roe_yoy
    bps_yoy assets_yoy eqt_yoy tr_yoy or_yoy q_sales_yoy q_op_qoq equity_yoy diluted_roe
    yoy_net_profit p_change_min p_change_max winner_rate net_amount_rate buy_elg_amount_rate
    buy_lg_amount_rate buy_md_amount_rate buy_sm_amount_rate swing weight m3 m6 y1 y3 y5 y7 y10 y30
    fr001 fr007 fr014 fdr001 fdr007 fdr014 nt_yoy nt_mom nt_accu town_yoy town_mom town_accu cnt_yoy
    cnt_mom cnt_accu ppi_yoy ppi_mp_yoy ppi_mp_qm_yoy ppi_mp_rm_yoy ppi_mp_p_yoy ppi_cg_yoy
    ppi_cg_f_yoy ppi_cg_c_yoy ppi_cg_adu_yoy ppi_cg_dcg_yoy ppi_mom ppi_mp_mom ppi_mp_qm_mom
    ppi_mp_rm_mom ppi_mp_p_mom ppi_cg_mom ppi_cg_f_mom ppi_cg_c_mom ppi_cg_adu_mom ppi_cg_dcg_mom
    ppi_accu ppi_mp_accu ppi_mp_qm_accu ppi_mp_rm_accu ppi_mp_p_accu ppi_cg_accu ppi_cg_f_accu
    ppi_cg_c_accu ppi_cg_adu_accu ppi_cg_dcg_accu pmi010000 pmi010100 pmi010200 pmi010300 pmi010400
    pmi010401 pmi010402 pmi010403 pmi010500 pmi010501 pmi010502 pmi010503 pmi010600 pmi010601
    pmi010602 pmi010603 pmi010700 pmi010701 pmi010702 pmi010703 pmi010800 pmi010801 pmi010802
    pmi010803 pmi010900 pmi011000 pmi011100 pmi011200 pmi011300 pmi011400 pmi011500 pmi011600
    pmi011700 pmi011800 pmi011900 pmi012000 pmi020100 pmi020101 pmi020102 pmi020200 pmi020201
    pmi020202 pmi020300 pmi020301 pmi020302 pmi020400 pmi020401 pmi020402 pmi020500 pmi020501
    pmi020502 pmi020600 pmi020601 pmi020602 pmi020700 pmi020800 pmi020900 pmi021000 pmi030000
    gdp_yoy pi_yoy si_yoy ti_yoy value forecast prev big_before big_after big_change sml_before
    sml_after sml_change ratio net_rate amount_rate buy_rate sell_rate dyr
    """)

# ── 单位：天 ──
U("天", """turn_days downdays updays lowdays topdays
    """)

# ── 单位：点 ──
U("点", """base_point bbi_bfq boll_lower_bfq boll_mid_bfq boll_upper_bfq dfma_dif_bfq dfma_difma_bfq
    madpo_bfq ema_bfq_10 ema_bfq_20 ema_bfq_250 ema_bfq_30 ema_bfq_5 ema_bfq_60 ema_bfq_90 maemv_bfq
    expma_12_bfq expma_50_bfq ktn_down_bfq ktn_mid_bfq ktn_upper_bfq ma_bfq_10 ma_bfq_20 ma_bfq_250
    ma_bfq_30 ma_bfq_5 ma_bfq_60 ma_bfq_90 ma_mass_bfq mtmma_bfq psyma_bfq maroc_bfq taq_down_bfq
    taq_mid_bfq taq_up_bfq trma_bfq xsii_td1_bfq xsii_td2_bfq xsii_td3_bfq xsii_td4_bfq avg_price
    index_value
    """)

# ── 单位：无量纲数值（新增字段；v1 无此单位，用 "1" 表示「以 1 计」）──
U("1", """asi_bfq asit_bfq atr_bfq bias1_bfq bias2_bfq bias3_bfq brar_ar_bfq brar_br_bfq cci_bfq cr_bfq
    dmi_adx_bfq dmi_adxr_bfq dmi_mdi_bfq dmi_pdi_bfq dpo_bfq emv_bfq kdj_bfq kdj_d_bfq kdj_k_bfq
    macd_bfq macd_dea_bfq macd_dif_bfq mass_bfq mfi_bfq mtm_bfq obv_bfq psy_bfq roc_bfq rsi_bfq_12
    rsi_bfq_24 rsi_bfq_6 trix_bfq vr_bfq wr_bfq wr1_bfq nt_val town_val cnt_val rank
    """)

# ── 单位：非数值（文本/代码/布尔；沿用 v1 契约，unit 输出空串 ""）──
U("", """name area industry fullname enname cnspell market exchange curr_type list_status is_hs list_date
    report_type comp_type end_type update_flag publisher category trade_unit per_unit quote_unit
    quote_unit_desc d_mode_desc d_month is_open perf_summary type summary change_reason next_sh
    next_sz note audit_result audit_agency audit_sign title market_type reason exalter side
    report_title classify org_name author_name quarter rating imp_dg
    """)


# ── 兼容性钉死：v1 既有字段的主表保持不变（不随 prio 泛化漂移）──
PRIMARY: dict[str, str] = {
    "total_share": "daily_basic",   # v1 主表 daily_basic / 单位 万股；balancesheet 是报告期末口径（股），不应抢主
}


# ── 派生常量 ──
DATASET_HISTORICAL: dict[str, bool] = {t: m["historical"] for t, m in DATASET.items()}
STATIC_ONLY_APIS = {t for t, m in DATASET.items() if not m["historical"]}
_DAILY_APIS = {t for t, m in DATASET.items() if m["family"] == Family.DAILY}
_FINA_APIS = {t for t, m in DATASET.items() if m["family"] == Family.PERIOD}
_EVENT_APIS = {t for t, m in DATASET.items() if m["family"] == Family.EVENT}
# 无 A 股 ts_code 标的的表（宏观/利率/全市场/日历）—— 缺口 4：从注册表 asset 维度推导，而非硬编码。
# 注意：trade_cal 的 entity 是 exchange、macro_bank 的 entity 是 name，都不是 None，
# 但同属「无需 A 股标的」的品类，故按 asset 维度判定（与 v1.2 的 _NO_TARGET_APIS 一致且为超集）。
_NO_TARGET_APIS = {t for t, m in DATASET.items() if m["asset"] in (Asset.MARKET, Asset.MACRO, Asset.RATE)}
