import matplotlib.pyplot as plt


def plot_dispatch(df, path):
    fig, ax = plt.subplots(figsize=(10,3))
    ax.plot(df.index, df["soc"], label="SoC")
    ax2 = ax.twinx()
    ax2.plot(df.index, df["pch"], label="Pch")
    ax2.plot(df.index, df["pdis"], label="Pdis")
    ax.set_title("Dispatch and SoC")
    ax.set_ylabel("SoC [-]"); ax2.set_ylabel("Power [kW]")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_kpi_bars(kpi_base, kpi_batt, kpi_full, path):
    labels = ["Baseline","Batt-aware","Batt+PV-aware"]
    metrics = ["annual_cost_gbp","equivalent_full_cycles","co2_avoided_kg"]
    for m in metrics:
        fig, ax = plt.subplots(figsize=(5,3))
        vals = [kpi_base.get(m,0), kpi_batt.get(m,0), kpi_full.get(m,0)]
        ax.bar(labels, vals)
        ax.set_title(m)
        fig.tight_layout()
        fig.savefig(path.replace(".png", f"_{m}.png"), dpi=150)
        plt.close(fig)