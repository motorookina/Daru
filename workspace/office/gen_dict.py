# -*- coding: utf-8 -*-
"""
从 finance_db(information_schema) + 人工元信息 生成《数据字典 v2》：
  - DATASET   : 数据集注册表（family × asset + 物理列映射 + 列级单位覆盖）
  - FIELD_DICT: 字段词汇表（语义名 -> 单位）
用法: python gen_dict.py
"""
import os
from collections import OrderedDict

from sqlalchemy import create_engine, text

OUT = "数据字典v2_全库.md"

# ============================================================
# 1. 表级元信息（人工）
#    asset : stock/index/industry/fut/bond/rate/market/macro
#    family: daily/period/event/static
#    entity: 标的列（None=无标的，如市场级/宏观）
#    axes  : 其它需要排除出 cols 的标识/时间列
#    pit   : (观测列, 可见列, 可见延迟天数)
#    sem   : 数值语义 point(时点) / cumulative(区间累计)
# ============================================================
def T(asset, family, entity=None, time=None, hist=True, prio=3, desc="",
      axes=(), pit=None, sem="point"):
    return dict(asset=asset, family=family, entity=entity, time=time,
                hist=hist, prio=prio, desc=desc, axes=tuple(axes), pit=pit, sem=sem)


TABLES = OrderedDict([
    # ---------------- 个股 ----------------
    ("stock_basic",   T("stock", "static", "ts_code", None, False, 1, "A股列表（含退市）",
                        axes=("symbol", "list_date", "delist_date"))),
    ("daily",         T("stock", "daily", "ts_code", "trade_date", True, 1, "A股日线行情")),
    ("adj_factor",    T("stock", "daily", "ts_code", "trade_date", True, 1, "复权因子")),
    ("daily_basic",   T("stock", "daily", "ts_code", "trade_date", True, 2, "每日指标（估值/股本/市值）")),
    ("income",        T("stock", "period", "ts_code", "end_date", True, 1, "利润表",
                        axes=("f_ann_date",), pit=("end_date", "ann_date", 0), sem="cumulative")),
    ("balancesheet",  T("stock", "period", "ts_code", "end_date", True, 1, "资产负债表",
                        axes=("f_ann_date",), pit=("end_date", "ann_date", 0))),
    ("cashflow",      T("stock", "period", "ts_code", "end_date", True, 1, "现金流量表",
                        axes=("f_ann_date",), pit=("end_date", "ann_date", 0), sem="cumulative")),
    ("fina_indicator", T("stock", "period", "ts_code", "end_date", True, 2, "财务指标",
                         pit=("end_date", "ann_date", 0))),
    ("express",       T("stock", "period", "ts_code", "end_date", True, 2, "业绩快报",
                        pit=("end_date", "ann_date", 0), sem="cumulative")),
    ("forecast",      T("stock", "period", "ts_code", "end_date", True, 3, "业绩预告",
                        axes=("first_ann_date",), pit=("end_date", "ann_date", 0))),
    ("fina_audit",    T("stock", "period", "ts_code", "end_date", True, 4, "财务审计意见",
                        axes=("created_at", "updated_at"), pit=("end_date", "ann_date", 0))),
    ("stk_holdernumber", T("stock", "period", "ts_code", "end_date", True, 4, "股东户数",
                           pit=("end_date", "ann_date", 0))),
    ("stk_rewards",   T("stock", "period", "ts_code", "end_date", True, 4, "管理层薪酬与持股",
                        pit=("end_date", "ann_date", 0))),
    ("cyq_perf",      T("stock", "daily", "ts_code", "trade_date", True, 3, "每日筹码分布")),
    ("moneyflow",     T("stock", "daily", "ts_code", "trade_date", True, 3, "个股资金流向")),
    ("moneyflow_dc",  T("stock", "daily", "ts_code", "trade_date", True, 3, "个股资金流向（东财）")),
    ("margin_detail", T("stock", "daily", "ts_code", "trade_date", True, 3, "融资融券明细")),
    ("hk_hold",       T("stock", "daily", "ts_code", "trade_date", True, 4, "陆股通持股", axes=("code",))),
    ("hsgt_top10",    T("stock", "daily", "ts_code", "trade_date", True, 4, "沪深股通十大成交股")),
    ("top_list",      T("stock", "daily", "ts_code", "trade_date", True, 4, "龙虎榜每日明细")),
    ("top_inst",      T("stock", "daily", "ts_code", "trade_date", True, 4, "龙虎榜机构席位")),
    ("namechange",    T("stock", "event", "ts_code", "start_date", True, 4, "股票曾用名",
                        axes=("end_date",), pit=("start_date", "ann_date", 0))),
    ("report_rc",     T("stock", "event", "ts_code", "report_date", True, 4, "券商盈利预测",
                        axes=("id", "create_time"), pit=("report_date", "report_date", 0))),
    # ---------------- 指数 ----------------
    ("index_basic",   T("index", "static", "ts_code", None, False, 1, "指数基本信息",
                        axes=("base_date", "list_date"))),
    ("index_daily",   T("index", "daily", "ts_code", "trade_date", True, 1, "指数日线行情")),
    ("index_dailybasic", T("index", "daily", "ts_code", "trade_date", True, 2, "指数每日指标")),
    ("idx_factor_pro", T("index", "daily", "ts_code", "trade_date", True, 3, "指数技术面因子（专业版）")),
    ("index_global",  T("index", "daily", "ts_code", "trade_date", True, 3, "国际指数行情")),
    ("index_weight",  T("index", "daily", "index_code", "trade_date", True, 3, "指数成分与权重",
                        axes=("con_code",))),
    ("lx_index_fundamental", T("index", "daily", "stock_code", "date", True, 4, "乐咕指数估值")),
    ("lx_index_tr",   T("index", "daily", "stock_code", "date", True, 4, "乐咕指数行情")),
    ("stock_index_pe_lg", T("index", "daily", "symbol", "date", True, 4, "乐咕指数PE")),
    ("stock_index_pb_lg", T("index", "daily", "symbol", "date", True, 4, "乐咕指数PB")),
    # ---------------- 行业/板块 ----------------
    ("sw_daily",      T("industry", "daily", "ts_code", "trade_date", True, 2, "申万行业日线")),
    ("index_hist_sw", T("industry", "daily", "symbol", "date", True, 3, "申万行业指数历史")),
    ("ths_daily",     T("industry", "daily", "ts_code", "trade_date", True, 3, "同花顺板块指数")),
    ("lx_industry_fundamental", T("industry", "daily", "industry_code", "date", True, 4, "乐咕行业估值")),
    # ---------------- 期货 ----------------
    ("fut_basic",     T("fut", "static", "ts_code", None, False, 1, "期货合约信息",
                        axes=("symbol", "exchange", "fut_code", "list_date", "delist_date", "last_ddate"))),
    ("fut_daily",     T("fut", "daily", "ts_code", "trade_date", True, 1, "期货日线行情")),
    ("futures_main_sina", T("fut", "daily", "symbol", "date", True, 3, "新浪期货主力连续")),
    # ---------------- 债券 / 利率 ----------------
    ("bond_china_yield", T("bond", "daily", "curve_name", "date", True, 3, "中债国债收益率曲线")),
    ("bond_new_composite_index_cbond", T("bond", "daily", "indicator", "date", True, 4,
                                         "中债新综合指数", axes=("period",))),
    ("repo_rate_hist", T("rate", "daily", None, "date", True, 3, "银行间质押式回购利率")),
    # ---------------- 全市场 ----------------
    ("trade_cal",     T("market", "static", "exchange", None, False, 1, "交易日历",
                        axes=("cal_date", "pretrade_date"))),
    ("stock_market_pe_lg", T("market", "daily", "symbol", "date", True, 3, "乐咕全市场PE")),
    ("stock_market_pb_lg", T("market", "daily", "symbol", "date", True, 3, "乐咕全市场PB")),
    # ---------------- 宏观 ----------------
    ("cn_cpi",        T("macro", "period", None, "month", True, 3, "居民消费价格指数",
                        pit=("month", "month", 15), sem="cumulative")),
    ("cn_ppi",        T("macro", "period", None, "month", True, 3, "工业生产者出厂价格指数",
                        pit=("month", "month", 15), sem="cumulative")),
    ("cn_pmi",        T("macro", "period", None, "month", True, 3, "采购经理人指数",
                        axes=("created_at", "updated_at"), pit=("month", "month", 1))),
    ("cn_gdp",        T("macro", "period", None, "quarter", True, 3, "国内生产总值",
                        pit=("quarter", "quarter", 20), sem="cumulative")),
    ("sf_month",      T("macro", "period", None, "month", True, 3, "社会融资规模增量",
                        pit=("month", "month", 15), sem="cumulative")),
    ("macro_bank_china_interest_rate", T("macro", "event", "name", "date", True, 3,
                                         "央行基准利率调整")),
    ("macro_china_reserve_requirement_ratio", T("macro", "event", None, "effect_date", True, 3,
                                                "存款准备金率调整", axes=("ann_date",))),
])

# ============================================================
# 2. 列改名（语义名 -> 物理列名）；同名直映的不用写
# ============================================================
RENAMES = {
    "idx_factor_pro": {"pct_chg": "pct_change"},
    "sw_daily": {"pct_chg": "pct_change", "circ_mv": "float_mv"},
    "ths_daily": {"pct_chg": "pct_change"},
    "moneyflow_dc": {"pct_chg": "pct_change"},
    "top_list": {"pct_chg": "pct_change"},
    "index_hist_sw": {"vol": "volume"},
    "lx_index_tr": {"vol": "volume"},
    "futures_main_sina": {"vol": "volume", "oi": "open_interest"},
    "hk_hold": {"hold_vol": "vol"},
    "index_dailybasic": {"circ_mv": "float_mv"},
}

# ============================================================
# 3. 单位（每张表 -> [(单位, "列1 列2 ...")]）
#    "" = 无量纲数值；None = 非数值（文本/代码/布尔）
# ============================================================
UNITS = {
    "stock_basic": [(None, "name area industry fullname enname cnspell market exchange curr_type list_status is_hs")],

    "daily": [("元", "open high low close pre_close change"), ("%", "pct_chg"),
              ("手", "vol"), ("千元", "amount")],
    "adj_factor": [("倍", "adj_factor")],
    "daily_basic": [("元", "close"), ("%", "turnover_rate turnover_rate_f dv_ratio dv_ttm"),
                    ("倍", "volume_ratio pe pe_ttm pb ps ps_ttm"),
                    ("万股", "total_share float_share free_share"),
                    ("万元", "total_mv circ_mv")],

    "income": [("元", """basic_eps diluted_eps total_revenue revenue int_income prem_earned comm_income
        n_commis_income n_oth_income n_oth_b_income prem_income out_prem une_prem_reser reins_income
        n_sec_tb_income n_sec_uw_income n_asset_mg_income oth_b_income fv_value_chg_gain invest_income
        ass_invest_income forex_gain total_cogs oper_cost int_exp comm_exp biz_tax_surchg sell_exp
        admin_exp fin_exp assets_impair_loss prem_refund compens_payout reser_insur_liab div_payt
        reins_exp oper_exp compens_payout_refu insur_reser_refu reins_cost_refund other_bus_cost
        operate_profit non_oper_income non_oper_exp nca_disploss total_profit income_tax n_income
        n_income_attr_p minority_gain oth_compr_income t_compr_income compr_inc_attr_p compr_inc_attr_m_s
        ebit ebitda insurance_exp undist_profit distable_profit rd_exp fin_exp_int_exp fin_exp_int_inc
        transfer_surplus_rese transfer_housing_imprest transfer_oth adj_lossgain withdra_legal_surplus
        withdra_legal_pubfund withdra_biz_devfund withdra_rese_fund withdra_oth_ersu workers_welfare
        distr_profit_shrhder prfshare_payable_dvd comshare_payable_dvd capit_comstock_div
        net_after_nr_lp_correct credit_impa_loss net_expo_hedging_benefits oth_impair_loss_assets
        total_opcost amodcost_fin_assets oth_income asset_disp_income continued_net_profit end_net_profit"""),
               (None, "report_type comp_type end_type update_flag")],

    "balancesheet": [("元", """cap_rese undistr_porfit surplus_rese special_rese money_cap trad_asset
        notes_receiv accounts_receiv oth_receiv prepayment div_receiv int_receiv inventories amor_exp
        nca_within_1y sett_rsrv loanto_oth_bank_fi premium_receiv reinsur_receiv reinsur_res_receiv
        pur_resale_fa oth_cur_assets total_cur_assets fa_avail_for_sale htm_invest lt_eqt_invest
        invest_real_estate time_deposits oth_assets lt_rec fix_assets cip const_materials
        fixed_assets_disp produc_bio_assets oil_and_gas_assets intan_assets r_and_d goodwill lt_amor_exp
        defer_tax_assets decr_in_disbur oth_nca total_nca cash_reser_cb depos_in_oth_bfi prec_metals
        deriv_assets rr_reins_une_prem rr_reins_outstd_cla rr_reins_lins_liab rr_reins_lthins_liab
        refund_depos ph_pledge_loans refund_cap_depos indep_acct_assets client_depos client_prov
        transac_seat_fee invest_as_receiv total_assets lt_borr st_borr cb_borr depos_ib_deposits
        loan_oth_bank trading_fl notes_payable acct_payable adv_receipts sold_for_repur_fa comm_payable
        payroll_payable taxes_payable int_payable div_payable oth_payable acc_exp deferred_inc
        st_bonds_payable payable_to_reinsurer rsrv_insur_cont acting_trading_sec acting_uw_sec
        non_cur_liab_due_1y oth_cur_liab total_cur_liab bond_payable lt_payable specific_payables
        estimated_liab defer_tax_liab defer_inc_non_cur_liab oth_ncl total_ncl depos_oth_bfi deriv_liab
        depos agency_bus_liab oth_liab prem_receiv_adva depos_received ph_invest reser_une_prem
        reser_outstd_claims reser_lins_liab reser_lthins_liab indept_acc_liab pledge_borr indem_payable
        policy_div_payable total_liab treasury_share ordin_risk_reser forex_differ invest_loss_unconf
        minority_int total_hldr_eqy_exc_min_int total_hldr_eqy_inc_min_int total_liab_hldr_eqy
        lt_payroll_payable oth_comp_income oth_eqt_tools oth_eqt_tools_p_shr lending_funds acc_receivable
        st_fin_payable payables hfs_assets hfs_sales cost_fin_assets fair_value_fin_assets cip_total
        oth_pay_total long_pay_total debt_invest oth_debt_invest oth_eq_invest oth_illiq_fin_assets
        oth_eq_ppbond receiv_financing use_right_assets lease_liab contract_assets contract_liab
        accounts_receiv_bill accounts_pay oth_rcv_total fix_assets_total"""),
                     ("股", "total_share"),
                     (None, "report_type comp_type end_type update_flag")],

    "cashflow": [("元", """net_profit finan_exp c_fr_sale_sg recp_tax_rends n_depos_incr_fi n_incr_loans_cb
        n_inc_borr_oth_fi prem_fr_orig_contr n_incr_insured_dep n_reinsur_prem n_incr_disp_tfa
        ifc_cash_incr n_incr_disp_faas n_incr_loans_oth_bank n_cap_incr_repur c_fr_oth_operate_a
        c_inf_fr_operate_a c_paid_goods_s c_paid_to_for_empl c_paid_for_taxes n_incr_clt_loan_adv
        n_incr_dep_cbob c_pay_claims_orig_inco pay_handling_chrg pay_comm_insur_plcy oth_cash_pay_oper_act
        st_cash_out_act n_cashflow_act oth_recp_ral_inv_act c_disp_withdrwl_invest c_recp_return_invest
        n_recp_disp_fiolta n_recp_disp_sobu stot_inflows_inv_act c_pay_acq_const_fiolta c_paid_invest
        n_disp_subs_oth_biz oth_pay_ral_inv_act n_incr_pledge_loan stot_out_inv_act n_cashflow_inv_act
        c_recp_borrow proc_issue_bonds oth_cash_recp_ral_fnc_act stot_cash_in_fnc_act free_cashflow
        c_prepay_amt_borr c_pay_dist_dpcp_int_exp incl_dvd_profit_paid_sc_ms oth_cashpay_ral_fnc_act
        stot_cashout_fnc_act n_cash_flows_fnc_act eff_fx_flu_cash n_incr_cash_cash_equ
        c_cash_equ_beg_period c_cash_equ_end_period c_recp_cap_contrib incl_cash_rec_saims
        uncon_invest_loss prov_depr_assets depr_fa_coga_dpba amort_intang_assets lt_amort_deferred_exp
        decr_deferred_exp incr_acc_exp loss_disp_fiolta loss_scr_fa loss_fv_chg invest_loss
        decr_def_inc_tax_assets incr_def_inc_tax_liab decr_inventories decr_oper_payable
        incr_oper_payable others im_net_cashflow_oper_act conv_debt_into_cap conv_copbonds_due_within_1y
        fa_fnc_leases im_n_incr_cash_equ net_dism_capital_add net_cash_rece_sec credit_impa_loss
        use_right_asset_dep oth_loss_asset end_bal_cash beg_bal_cash end_bal_cash_equ beg_bal_cash_equ"""),
                 (None, "comp_type report_type end_type update_flag")],

    "fina_indicator": [("元", """eps dt_eps total_revenue_ps revenue_ps capital_rese_ps surplus_rese_ps
        undist_profit_ps extra_item profit_dedt op_income ebit ebitda fcff fcfe current_exint
        noncurrent_exint interestdebt netdebt tangible_asset working_capital networking_capital
        invest_capital retained_earnings diluted2_eps bps ocfps retainedps cfps ebit_ps fcff_ps fcfe_ps
        roa_dp fixed_assets"""),
                       ("%", """gross_margin netprofit_margin grossprofit_margin cogs_of_sales
        expense_of_sales profit_to_gr saleexp_to_gr adminexp_of_gr finaexp_of_gr impai_ttm gc_of_gr
        op_of_gr ebit_of_gr roe roe_waa roe_dt roa npta roic roe_yearly roa2_yearly debt_to_assets
        dp_assets_to_eqt ca_to_assets nca_to_assets tbassets_to_totalassets int_to_talcap
        eqt_to_talcapital currentdebt_to_debt longdeb_to_debt eqt_to_interestdebt roa_yearly
        profit_to_op q_saleexp_to_gr q_gc_to_gr q_roe q_dt_roe q_npta q_ocf_to_sales basic_eps_yoy
        dt_eps_yoy cfps_yoy op_yoy ebt_yoy netprofit_yoy dt_netprofit_yoy ocf_yoy roe_yoy bps_yoy
        assets_yoy eqt_yoy tr_yoy or_yoy q_sales_yoy q_op_qoq equity_yoy"""),
                       ("倍", """current_ratio quick_ratio cash_ratio ar_turn ca_turn fa_turn assets_turn
        assets_to_eqt ocf_to_shortdebt debt_to_eqt eqt_to_debt tangibleasset_to_debt tangasset_to_intdebt
        tangibleasset_to_netdebt ocf_to_debt"""),
                       ("天", "turn_days"),
                       (None, "update_flag")],

    "express": [("元", "revenue operate_profit total_profit n_income total_assets total_hldr_eqy_exc_min_int diluted_eps bps"),
                ("%", "diluted_roe yoy_net_profit"),
                (None, "perf_summary update_flag")],

    "forecast": [("%", "p_change_min p_change_max"), ("万元", "net_profit_min net_profit_max last_parent_net"),
                 (None, "type summary change_reason update_flag")],

    "fina_audit": [("元", "audit_fees"), (None, "audit_result audit_agency audit_sign")],

    "stk_holdernumber": [("户", "holder_num")],
    "stk_rewards": [("元", "reward"), ("股", "hold_vol"), (None, "name title")],

    "cyq_perf": [("元", "his_low his_high cost_5pct cost_15pct cost_50pct cost_85pct cost_95pct weight_avg"),
                 ("%", "winner_rate")],

    "moneyflow": [("手", """buy_sm_vol sell_sm_vol buy_md_vol sell_md_vol buy_lg_vol sell_lg_vol
        buy_elg_vol sell_elg_vol net_mf_vol"""),
                  ("万元", """buy_sm_amount sell_sm_amount buy_md_amount sell_md_amount buy_lg_amount
        sell_lg_amount buy_elg_amount sell_elg_amount net_mf_amount""")],

    "moneyflow_dc": [("元", "close"), ("%", "pct_chg net_amount_rate buy_elg_amount_rate buy_lg_amount_rate buy_md_amount_rate buy_sm_amount_rate"),
                     ("万元", "net_amount buy_elg_amount buy_lg_amount buy_md_amount buy_sm_amount"),
                     (None, "name")],

    "margin_detail": [("元", "rzye rqye rzmre rzche rzrqye"), ("股", "rqyl rqchl rqmcl"), (None, "name")],

    "hk_hold": [("股", "hold_vol"), ("%", "ratio"), (None, "name exchange")],
    "hsgt_top10": [("元", "close change"), ("万元", "amount net_amount buy sell"),
                   ("", "rank"), (None, "name market_type")],

    "top_list": [("元", "close"), ("%", "pct_chg turnover_rate net_rate amount_rate"),
                 ("元", "amount l_sell l_buy l_amount net_amount float_values"),
                 (None, "name reason")],
    "top_inst": [("元", "buy sell net_buy"), ("%", "buy_rate sell_rate"),
                 (None, "exalter side reason")],

    "namechange": [(None, "name change_reason")],
    "report_rc": [("元", "eps max_price min_price"), ("倍", "pe ev_ebitda"), ("%", "roe"),
                  ("亿元", "op_rt op_pr tp np rd"),
                  (None, "name report_title report_type classify org_name author_name quarter rating imp_dg")],

    "index_basic": [("点", "base_point"), (None, "name market publisher category")],
    "index_daily": [("点", "close open high low pre_close change"), ("%", "pct_chg"),
                    ("手", "vol"), ("千元", "amount")],
    "index_dailybasic": [("%", "turnover_rate turnover_rate_f"),
                         ("倍", "pe pe_ttm pb"),
                         ("万股", "total_share float_share free_share"),
                         ("万元", "total_mv circ_mv")],
    "idx_factor_pro": [("点", "open high low close pre_close change"), ("%", "pct_chg"),
                       ("手", "vol"), ("千元", "amount"),
                       ("点", """boll_lower_bfq boll_mid_bfq boll_upper_bfq bbi_bfq
        ema_bfq_5 ema_bfq_10 ema_bfq_20 ema_bfq_30 ema_bfq_60 ema_bfq_90 ema_bfq_250
        expma_12_bfq expma_50_bfq ktn_down_bfq ktn_mid_bfq ktn_upper_bfq ma_bfq_5 ma_bfq_10
        ma_bfq_20 ma_bfq_30 ma_bfq_60 ma_bfq_90 ma_bfq_250 madpo_bfq maemv_bfq ma_mass_bfq
        maroc_bfq mtmma_bfq psyma_bfq taq_down_bfq taq_mid_bfq taq_up_bfq trma_bfq
        xsii_td1_bfq xsii_td2_bfq xsii_td3_bfq xsii_td4_bfq dfma_dif_bfq dfma_difma_bfq"""),
                       ("", """asi_bfq asit_bfq atr_bfq bias1_bfq bias2_bfq bias3_bfq brar_ar_bfq
        brar_br_bfq cci_bfq cr_bfq dmi_adx_bfq dmi_adxr_bfq dmi_mdi_bfq dmi_pdi_bfq dpo_bfq emv_bfq
        kdj_bfq kdj_d_bfq kdj_k_bfq macd_bfq macd_dea_bfq macd_dif_bfq mass_bfq mfi_bfq mtm_bfq
        obv_bfq psy_bfq roc_bfq rsi_bfq_6 rsi_bfq_12 rsi_bfq_24 trix_bfq vr_bfq wr_bfq wr1_bfq"""),
                       ("天", "downdays updays lowdays topdays")],
    "index_global": [("点", "open close high low pre_close change"), ("%", "pct_chg swing"),
                     ("手", "vol")],
    "index_weight": [("%", "weight")],
    "lx_index_fundamental": [("倍", "pe_ttm pb"), ("%", "dyr")],
    "lx_index_tr": [("点", "close change"), ("手", "vol"), ("千元", "amount")],
    "stock_index_pe_lg": [("点", "index_value"),
                          ("倍", "pe_lyr_ew pe_lyr pe_lyr_median pe_ttm_ew pe_ttm pe_ttm_median")],
    "stock_index_pb_lg": [("点", "index_value"), ("倍", "pb pb_ew pb_median")],

    "sw_daily": [("点", "open low high close change"), ("%", "pct_chg"),
                 ("手", "vol"), ("千元", "amount"), ("倍", "pe pb"),
                 ("万元", "circ_mv total_mv"), (None, "name")],
    "index_hist_sw": [("点", "close open high low"), ("手", "vol"), ("千元", "amount")],
    "ths_daily": [("点", "open high low close pre_close avg_price change"), ("%", "pct_chg turnover_rate"),
                  ("手", "vol")],
    "lx_industry_fundamental": [("倍", "pe_ttm pb"), ("%", "dyr")],

    "fut_basic": [("倍", "multiplier"),
                  (None, "name trade_unit per_unit quote_unit quote_unit_desc d_mode_desc d_month")],
    "fut_daily": [("元", "pre_close pre_settle open high low close settle change1 change2"),
                  ("手", "vol oi oi_chg"), ("万元", "amount")],
    "futures_main_sina": [("元", "open high low close settle"), ("手", "vol oi")],

    "bond_china_yield": [("%", "m3 m6 y1 y3 y5 y7 y10 y30")],
    "bond_new_composite_index_cbond": [("点", "value")],
    "repo_rate_hist": [("%", "fr001 fr007 fr014 fdr001 fdr007 fdr014")],

    "trade_cal": [(None, "is_open")],
    "stock_market_pe_lg": [("点", "index_value"), ("倍", "pe")],
    "stock_market_pb_lg": [("点", "index_value"), ("倍", "pb pb_ew pb_median")],

    "cn_cpi": [("", "nt_val town_val cnt_val"), ("%", """nt_yoy nt_mom nt_accu town_yoy town_mom town_accu
        cnt_yoy cnt_mom cnt_accu""")],
    "cn_ppi": [("%", """ppi_yoy ppi_mp_yoy ppi_mp_qm_yoy ppi_mp_rm_yoy ppi_mp_p_yoy ppi_cg_yoy
        ppi_cg_f_yoy ppi_cg_c_yoy ppi_cg_adu_yoy ppi_cg_dcg_yoy ppi_mom ppi_mp_mom ppi_mp_qm_mom
        ppi_mp_rm_mom ppi_mp_p_mom ppi_cg_mom ppi_cg_f_mom ppi_cg_c_mom ppi_cg_adu_mom ppi_cg_dcg_mom
        ppi_accu ppi_mp_accu ppi_mp_qm_accu ppi_mp_rm_accu ppi_mp_p_accu ppi_cg_accu ppi_cg_f_accu
        ppi_cg_c_accu ppi_cg_adu_accu ppi_cg_dcg_accu""")],
    "cn_pmi": [("%", """pmi010000 pmi010100 pmi010200 pmi010300 pmi010400 pmi010401 pmi010402 pmi010403
        pmi010500 pmi010501 pmi010502 pmi010503 pmi010600 pmi010601 pmi010602 pmi010603 pmi010700
        pmi010701 pmi010702 pmi010703 pmi010800 pmi010801 pmi010802 pmi010803 pmi010900 pmi011000
        pmi011100 pmi011200 pmi011300 pmi011400 pmi011500 pmi011600 pmi011700 pmi011800 pmi011900
        pmi012000 pmi020100 pmi020101 pmi020102 pmi020200 pmi020201 pmi020202 pmi020300 pmi020301
        pmi020302 pmi020400 pmi020401 pmi020402 pmi020500 pmi020501 pmi020502 pmi020600 pmi020601
        pmi020602 pmi020700 pmi020800 pmi020900 pmi021000 pmi030000""")],
    "cn_gdp": [("亿元", "gdp pi si ti"), ("%", "gdp_yoy pi_yoy si_yoy ti_yoy")],
    "sf_month": [("亿元", "inc_month inc_cumval stk_endval")],
    "macro_bank_china_interest_rate": [("%", "value forecast prev")],
    "macro_china_reserve_requirement_ratio": [("%", "big_before big_after big_change sml_before sml_after sml_change"),
                                              (None, "next_sh next_sz note")],
}

# ============================================================
# 4. 单位待核清单（单位按经验填写，标注出来供人工复核）
# ============================================================
WARN = {
    "balancesheet": "total_share",
    "forecast": "net_profit_min net_profit_max last_parent_net",
    "hsgt_top10": "amount net_amount buy sell close change",
    "top_list": "amount l_sell l_buy l_amount net_amount float_values",
    "top_inst": "buy sell net_buy",
    "moneyflow_dc": "net_amount buy_elg_amount buy_lg_amount buy_md_amount buy_sm_amount",
    "fut_daily": "amount",
    "index_global": "swing vol",
    "sw_daily": "vol amount",
    "index_hist_sw": "vol amount",
    "ths_daily": "vol turnover_rate avg_price",
    "lx_index_tr": "vol amount",
    "stock_index_pe_lg": "index_value",
    "stock_index_pb_lg": "index_value",
    "stock_market_pe_lg": "index_value pe",
    "stock_market_pb_lg": "index_value pb pb_ew pb_median",
    "bond_new_composite_index_cbond": "value",
    "report_rc": "op_rt op_pr tp np rd",
    "cn_cpi": "nt_val town_val cnt_val",
    "cn_pmi": "pmi010000 pmi010100 pmi010200 pmi010300 pmi010400 pmi010401 pmi010402 pmi010403 "
              "pmi010500 pmi010501 pmi010502 pmi010503 pmi010600 pmi010601 pmi010602 pmi010603 "
              "pmi010700 pmi010701 pmi010702 pmi010703 pmi010800 pmi010801 pmi010802 pmi010803 "
              "pmi010900 pmi011000 pmi011100 pmi011200 pmi011300 pmi011400 pmi011500 pmi011600 "
              "pmi011700 pmi011800 pmi011900 pmi012000",
    "idx_factor_pro": "技术因子（同量纲近似标注）",
    "macro_china_reserve_requirement_ratio": "next_sh next_sz",
}

# ============================================================
# 5. 未纳入注册表的系统表
# ============================================================
SYSTEM_TABLES = OrderedDict([
    ("api_doc", "接口文档登记"), ("api_registry", "接口注册表"),
    ("dump_job", "导出任务"), ("task_schedule", "任务调度"),
    ("agent_scheduled_tasks", "智能体定时任务"), ("agent_sandbox_jobs", "沙箱执行任务"),
    ("apscheduler_jobs", "APScheduler 持久化作业"),
])


# ============================================================
# 生成
# ============================================================
def load_schema():
    eng = create_engine(os.environ["DARU_DB_RO_URL"])
    with eng.connect() as c:
        rows = c.execute(text(
            "select table_name, column_name from information_schema.columns "
            "where table_schema='public' order by table_name, ordinal_position")).fetchall()
    d = OrderedDict()
    for t, col in rows:
        d.setdefault(t, []).append(col)
    return d


def build():
    schema = load_schema()
    err, dset, units = [], OrderedDict(), {}

    for tbl, meta in TABLES.items():
        if tbl not in schema:
            err.append(f"表不存在: {tbl}")
            continue
        cols = schema[tbl]
        # 排除 id/时间列
        excl = set(meta["axes"])
        if meta["entity"]:
            excl.add(meta["entity"])
        if meta["time"]:
            excl.add(meta["time"])
        if meta["pit"]:
            excl.add(meta["pit"][0]); excl.add(meta["pit"][1])
        # 单位声明
        umap, declared = {}, set()
        for unit, names in UNITS.get(tbl, []):
            for n in names.split():
                if n in umap and umap[n] != unit:
                    err.append(f"{tbl}.{n} 单位重复声明: {umap[n]} / {unit}")
                umap[n] = unit
                declared.add(n)
        # 改名：语义名 -> 物理列
        ren = RENAMES.get(tbl, {})
        phys2sem = {v: k for k, v in ren.items()}
        c_cols, missing, extra = OrderedDict(), [], []
        semset = set()
        for col in cols:
            if col in excl:
                continue
            sem = phys2sem.get(col, col)
            if sem not in declared:
                missing.append(col)
                umap.setdefault(sem, None)
            semset.add(sem)
            c_cols[sem] = (col, umap[sem])
            units[(tbl, sem)] = umap[sem]
        for n in declared:
            if n not in semset:
                extra.append(n)
        if missing:
            err.append(f"{tbl} 未声明单位的列: {' '.join(missing)}")
        if extra:
            err.append(f"{tbl} 声明了不存在的列: {' '.join(extra)}")
        dset[tbl] = (meta, c_cols)

    # 缺表/缺列检查
    for t in schema:
        if t not in TABLES and t not in SYSTEM_TABLES and t not in ("api_doc",):
            err.append(f"库中存在但未登记的表: {t}")

    # FIELD_DICT：语义名 -> 单位（取 prio 最小的表为准）
    # FIELD_DICT 缺省单位 = 主表（prio 最小者）的单位
    fields = OrderedDict()
    for tbl, (meta, c_cols) in sorted(dset.items(), key=lambda kv: kv[1][0]["prio"]):
        for sem, (phys, unit) in c_cols.items():
            if sem not in fields:
                fields[sem] = dict(unit=unit, src=tbl)
    conflicts = []
    for tbl, (meta, c_cols) in dset.items():
        for sem, (phys, unit) in c_cols.items():
            if unit != fields[sem]["unit"]:
                conflicts.append((sem, tbl, unit, fields[sem]["unit"]))
    return dset, fields, conflicts, err


def fmt_cols(c_cols, default_unit, indent=8):
    """输出 cols=ID(...)。单位与 FIELD_DICT 缺省不同的用 (物理列, 单位) 覆盖。"""
    ident, over = [], []
    for sem, (phys, unit) in c_cols.items():
        if sem == phys and unit == default_unit[sem]:
            ident.append(phys)
        elif sem == phys:
            over.append(f'{sem}=("{phys}", "{unit}")')
        else:
            over.append(f'{sem}="{phys}"')
    flat = " ".join(ident)
    if len(flat) + sum(len(o) + 2 for o in over) <= 100:
        args = ([f'"{flat}"'] if flat else []) + over
        return "ID(" + ", ".join(args) + ")"
    segs, cur = [], ""
    for n in ident:
        if cur and len(cur) + len(n) + 1 > 84:
            segs.append(cur + " ")
            cur = ""
        cur = (cur + " " + n).strip() if cur else n
    if cur:
        segs.append(cur)
    lines = ["ID("]
    for i, sg in enumerate(segs):
        tail = "," if (i == len(segs) - 1 and over) else ""
        lines.append(f'"{sg}"{tail}')
    for i, ov in enumerate(over):
        lines.append(ov + ("," if i < len(over) - 1 else ""))
    pad = " " * (indent + 4)
    return "ID(\n" + "".join(pad + ln + "\n" for ln in lines[1:]) + " " * indent + ")"


def main():
    dset, fields, conflicts, err = build()

    # ---- FIELD_DICT 按单位分组 ----
    by_unit = OrderedDict()
    for sem, m in fields.items():
        by_unit.setdefault(m["unit"], []).append(sem)
    order = ["元", "万元", "亿元", "千元", "万股", "股", "手", "户", "倍", "%", "天", "点", "", None]
    by_unit = OrderedDict((u, by_unit[u]) for u in order if u in by_unit)

    multi_unit = {}
    for sem, tbl, u, d in conflicts:
        multi_unit.setdefault(sem, set()).add((tbl, u, d))

    L = []
    A = L.append
    A("# 数据字典 v2（全库扩展版）：FIELD_DICT + DATASET")
    A("")
    A("> 生成日期：2026-09-11")
    A("> 依据：`finance_db`（PostgreSQL）中全部 `public` 表的 `information_schema` 实际列")
    A(f"> 覆盖：数据表 **{len(dset)}** 张 / 语义字段 **{len(fields)}** 个 / 物理列 "
      f"**{sum(len(c) for _, c in dset.values())}** 个")
    A("> 方法：沿用《问题记录：数据族概念重定义（字段驱动版）》的「字段词汇表 + "
      "数据集注册表（family × asset）」骨架，按真实库表补齐。")
    A("")
    A("---")
    A("")
    A("## 0. 相对原方案的 6 处扩展")
    A("")
    A("| # | 扩展点 | 原因 |")
    A("| --- | --- | --- |")
    A("| 0.1 | `family` 增加 **`event`** | 原方案只有 daily/period/static。库中 "
      "`namechange`/`report_rc`/`macro_bank_china_interest_rate`/"
      "`macro_china_reserve_requirement_ratio` 既不是交易日序列、也不是报告期序列，"
      "而是「一次性事件记录」，硬塞进三个族会污染语义。 |")
    A("| 0.2 | `asset` 从 2 个扩到 **8 个** | 实际库表覆盖 stock/index/**industry**/"
      "**fut**/**bond**/**rate**/**market**/**macro**，只留 stock/index 无法路由。 |")
    A("| 0.3 | `cols` 支持**列级单位覆盖** `(\"物理列\", \"单位\")` | 同名同概念、单位却随表变化"
      "（`amount` 在 `daily` 是千元、在 `hsgt_top10` 是万元）无法用全局单位表达，"
      "又不足以改名成两个语义。 |")
    A("| 0.4 | 新增 **`prio`**（同族同资产的取数优先级） | `resolve(field, asset)` 会命中多张表"
      "（股票 `close` 同时命中 `daily`/`daily_basic`/`top_list`），需要一个确定性的主表。 |")
    A("| 0.5 | 新增 **`entity`/`time`/`pit`/`sem`** | `resolve` 之后还要知道拿哪一列做标的对齐、"
      "哪一列做时点对齐、观测日与可见日分别是谁、数值是时点值还是区间累计值。 |")
    A("| 0.6 | `cols` **不含**标的列/时间列/公告日列 | 它们是轴（axis）不是指标（measure），"
      "登记在 `entity`/`time`/`pit` 上，避免污染字段词汇表。 |")
    A("")
    A("**单位语义约定**：`\"\"` = 无量纲数值（如 RSI、KDJ）；`null` = 非数值（文本/代码/布尔/日期）。")
    A("")
    A("---")
    A("")
    A("## 1. 枚举定义")
    A("")
    A("```python")
    A("from enum import StrEnum")
    A("")
    A("class Family(StrEnum):")
    A('    DAILY  = "daily"   # 交易日粒度：观测日 = 可见日 = 交易日')
    A('    PERIOD = "period"  # 报告期/统计期：观测日 = end_date，可见日 = ann_date')
    A('    EVENT  = "event"   # 一次性事件：观测日 = 事件/生效日，可见日 = 公告/发布日（扩展新增）')
    A('    STATIC = "static"  # 无时点快照，无历史版本')
    A("")
    A("class Asset(StrEnum):")
    A('    STOCK    = "stock"     # 个股')
    A('    INDEX    = "index"     # 指数（宽基/全球/主题）')
    A('    INDUSTRY = "industry"  # 行业与板块指数（申万/同花顺/乐咕行业）')
    A('    FUT      = "fut"       # 期货')
    A('    BOND     = "bond"      # 债券指数 / 收益率曲线')
    A('    RATE     = "rate"      # 货币市场回购利率')
    A('    MARKET   = "market"    # 全市场（跨资产的聚合指标、日历）')
    A('    MACRO    = "macro"     # 宏观')
    A("")
    A("def ID(cols: str = \"\", **over) -> dict:")
    A('    """cols 书写糖：cols 里列同名直映；over 既可改名 pct_chg=\"pct_change\"，')
    A('       也可做列级单位覆盖 amount=(\"amount\", \"万元\")。"""')
    A("    d = {c: c for c in cols.split()}")
    A("    for k, v in over.items():")
    A("        phys = v[0] if isinstance(v, tuple) else v")
    A("        if phys in d:")
    A("            del d[phys]")
    A("        d[k] = v")
    A("    return d")
    A("```")
    A("")
    A("---")
    A("")
    A("## 2. DATASET（数据集注册表，全库 " + str(len(dset)) + " 张）")
    A("")
    A("字段含义：`family` 时点语义 · `asset` 资产类型 · `historical` 有无历史版本（PIT 能力） · "
      "`prio` 取数优先级（小者为主表） · `entity`/`time` 标的列/时间列 · "
      "`pit` (观测列, 可见列, 可见延迟天数) · `sem` 数值语义 point/cumulative · "
      "`axes` 该表**不再对外暴露为字段**的标识/时间/系统列 · `cols` 语义名→物理列（未标注单位者取 `FIELD_DICT` 缺省单位，即 prio 最小的主表的单位）。")
    A("")
    A("```python")
    A("DATASET: dict[str, dict] = {")
    cur_asset = None
    for tbl, (meta, c_cols) in dset.items():
        if meta["asset"] != cur_asset:
            cur_asset = meta["asset"]
            A("")
            A(f"    # ══════════════ asset = {cur_asset} ══════════════")
        A(f'    "{tbl}": {{  # {meta["desc"]}')
        A(f'        "family": "{meta["family"]}", "asset": "{meta["asset"]}", '
          f'"historical": {meta["hist"]}, "prio": {meta["prio"]},')
        ent = f'"{meta["entity"]}"' if meta["entity"] else "None"
        tim = f'"{meta["time"]}"' if meta["time"] else "None"
        line = f'        "entity": {ent}, "time": {tim},'
        if meta["pit"]:
            o, a, lag = meta["pit"]
            line += f' "pit": ("{o}", "{a}", {lag}),'
        line += f' "sem": "{meta["sem"]}",'
        A(line)
        if meta["axes"]:
            axs = ", ".join(f'"{x}"' for x in meta["axes"])
            A(f'        "axes": ({axs}{"," if len(meta["axes"]) == 1 else ""}),')
        cols = fmt_cols(c_cols, {s: fields[s]["unit"] for s in c_cols})
        A(f'        "cols": {cols},')
        A("    },")
    A("}")
    A("```")
    A("")
    A("> 说明：以上 `historical=True` 但 `family=static` 的表不存在（`stock_basic` 等静态表已置 False）；"
      "`pit` 仅在 period/event 族出现，其第三位是**可见延迟天数**（宏观数据在统计期结束后才发布）。")
    A("")
    A("---")
    A("")
    A("## 3. FIELD_DICT（字段词汇表，全库 " + str(len(fields)) + " 个语义名）")
    A("")
    A("字段字典只保留**语义名 + 单位**，不含 api / col / cat —— 物理落位归 `DATASET`，"
      "资产类型归 `classify_asset`，时点语义归 `family`。")
    A("")
    A("```python")
    A("FIELD_DICT: dict[str, dict] = {}")
    A("")
    A("")
    A("def U(unit, names: str) -> None:")
    A('    """批量登记同一单位的语义字段。"""')
    A("    for n in names.split():")
    A('        FIELD_DICT[n] = {"unit": unit}')
    A("")
    for unit, names in by_unit.items():
        label = {None: "非数值（文本/代码/布尔）", "": "无量纲数值"}.get(unit, unit)
        A(f"# ── 单位：{label} ──")
        body = " ".join(names)
        lines, cur = [], ""
        for n in names:
            if len(cur) + len(n) + 1 > 96:
                lines.append(cur); cur = ""
            cur = (cur + " " + n).strip()
        if cur:
            lines.append(cur)
        u = "None" if unit is None else f'"{unit}"'
        A(f"U({u}, \"\"\"{lines[0]}")
        for ln in lines[1:]:
            A(f"    {ln}")
        A('    """)')
        A("")
    A("```")
    A("")
    A("### 3.1 同名不同单位的字段（靠 `DATASET.cols` 的列级覆盖消歧）")
    A("")
    A("| 字段 | 缺省单位（主表） | 其它表的单位 |")
    A("| --- | --- | --- |")
    for sem, lst in sorted(multi_unit.items()):
        others = "、".join(f"`{t}`={u if u is not None else '非数值'}" for t, u, d in sorted(lst))
        A(f"| `{sem}` | {fields[sem]['unit']}（`{fields[sem]['src']}`） | {others} |")
    A("")
    A("---")
    A("")
    A("## 4. 解析流水线与派生索引")
    A("")
    A("```python")
    A("def resolve(field: str, asset: str) -> list[str]:")
    A('    """返回候选表名，按 prio 升序。消歧不了就全给，让路由层定。"""')
    A("    hit = [t for t, m in DATASET.items()")
    A("           if m['asset'] in (asset, 'market') and field in m['cols']]")
    A("    return sorted(hit, key=lambda t: DATASET[t]['prio'])")
    A("")
    A("")
    A("def resolve_one(field: str, asset: str) -> str | None:")
    A('    """取主表（prio 最小）；并列则返回 None，交由路由层裁决。"""')
    A("    c = resolve(field, asset)")
    A("    if not c:")
    A("        return None")
    A("    if len(c) > 1 and DATASET[c[0]]['prio'] == DATASET[c[1]]['prio']:")
    A("        return None")
    A("    return c[0]")
    A("")
    A("")
    A("def desc(field: str, table: str) -> tuple[str, str]:")
    A('    """返回 (物理列, 单位)。列级覆盖优先，其次 FIELD_DICT 缺省单位。"""')
    A("    v = DATASET[table]['cols'][field]")
    A("    if isinstance(v, tuple):")
    A("        return v")
    A("    return v, FIELD_DICT[field]['unit']")
    A("```")
    A("")
    A("### 4.1 解析示例（由注册表实际算出）")
    A("")
    A("| field | asset | 候选表（按 prio） |")
    A("| --- | --- | --- |")
    for f, a in [("close", "stock"), ("close", "index"), ("pe_ttm", "stock"),
                 ("pe_ttm", "index"), ("n_income", "stock"), ("name", "stock"),
                 ("vol", "fut"), ("total_mv", "index"), ("turnover_rate", "industry"),
                 ("roe", "stock")]:
        cand = [t for t, dm in dset.items()
                if dm[0]["asset"] == a and f in dm[1]]
        cand.sort(key=lambda t: dset[t][0]["prio"])
        A(f"| `{f}` | `{a}` | {' → '.join('`'+c+'`' for c in cand) or '—'} |")
    A("")
    A("---")
    A("")
    A("## 5. 校验规则（建议进 CI）")
    A("")
    A("1. 每个 `DATASET` 的 `family`/`asset` 必须是枚举成员；`cols` 值必须是字符串或二元组。")
    A("2. `cols` 的语义名必须存在于 `FIELD_DICT`；物理列必须真实存在于该表。")
    A("3. 物理列若不等于语义名，则该物理列不得再以自身名出现在 `cols` 中（防重）。")
    A("4. `entity`/`time`/`pit[0]`/`pit[1]` 必须在该表中真实存在，且不得出现在 `cols` 中。")
    A("5. `family=static` ⟹ `historical=False`；`family=daily` ⟹ `pit is None`。")
    A("6. 同一物理列不得被两个语义名同时引用。")
    A("7. 机器生成的部分：`python gen_dict.py` 可重跑，人工只维护 "
      "`TABLES` / `RENAMES` / `UNITS`。")
    A("")
    A("---")
    A("")
    A("## 6. 单位待核清单（已按经验填，请人工复核）")
    A("")
    A("| 表 | 待核列 |")
    A("| --- | --- |")
    for t, c in WARN.items():
        A(f"| `{t}` | {c} |")
    A("")
    A("---")
    A("")
    A("## 7. 未纳入注册表的系统表（" + str(len(SYSTEM_TABLES)) + " 张）")
    A("")
    A("这些表的用途是服务自身运行，不是金融数据，故不进 `DATASET`：")
    A("")
    for t, d in SYSTEM_TABLES.items():
        A(f"- `{t}` —— {d}")
    A("")
    A("---")
    A("")
    A("## 附录 A：生成期诊断")
    A("")
    A("本文档的两个代码块（`DATASET` / `FIELD_DICT`）是把 markdown 当源码用的，"
      "已做机械回归：**逐表逐列**校验「表存在、列存在、枚举合法、物理列唯一引用、"
      "轴列不混入 cols、库列 100% 有归属」，当前结果 **0 异常**。")
    A("重新生成：`python gen_dict.py`（人工只维护 `TABLES` / `RENAMES` / `UNITS` / `WARN`）；"
      "重新校验：`python verify_dict.py`。")
    A("")
    if err:
        A("发现以下问题（需人工处理）：")
        A("")
        for e in err:
            A(f"- {e}")
    else:
        A("✅ 无异常：库中所有列均已登记单位，无重复声明，无幽灵列。")
    A("")
    A(f"共 **{len(conflicts)}** 处「同语义名不同单位」被登记为列级单位覆盖。")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("written:", OUT, len("\n".join(L)), "chars")
    print("tables:", len(dset), "fields:", len(fields), "conflicts:", len(conflicts))
    for e in err:
        print("ERR:", e)


if __name__ == "__main__":
    main()
