import { useTranslation } from "react-i18next";
import { Brain, Shield, Users, Heart } from "lucide-react";
import Disclaimer from "@/components/Disclaimer";

const About = () => {
  const { t } = useTranslation();

  const items = [
    { icon: Brain, title: t("about.ai_title"), desc: t("about.ai_desc") },
    { icon: Shield, title: t("about.privacy_title"), desc: t("about.privacy_desc") },
    { icon: Users, title: t("about.balance_title"), desc: t("about.balance_desc") },
    { icon: Heart, title: t("about.empathy_title"), desc: t("about.empathy_desc") },
  ];

  return (
    <div className="container max-w-3xl py-10 md:py-16">
      <h1 className="font-display text-3xl font-bold md:text-4xl text-center glow-text">{t("about.title")}</h1>
      <p className="mt-4 text-center text-muted-foreground max-w-xl mx-auto">
        {t("about.subtitle")}
      </p>

      <div className="mt-12 space-y-6">
        {items.map((item) => (
          <div key={item.title} className="glass-card p-6 flex items-start gap-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/20">
              <item.icon className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h3 className="font-display font-semibold">{item.title}</h3>
              <p className="mt-1 text-sm text-muted-foreground">{item.desc}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-10">
        <Disclaimer />
      </div>

      <div className="mt-6 text-center text-xs text-muted-foreground">
        <p>{t("about.project_info")}</p>
        <p>{t("about.group_id")}</p>
      </div>
    </div>
  );
};

export default About;
