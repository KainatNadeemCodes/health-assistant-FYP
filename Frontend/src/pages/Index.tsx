import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useTranslation } from "react-i18next";
import { Brain, Stethoscope, MessageCircle, Shield, Clock, Heart } from "lucide-react";
import { motion } from "framer-motion";
import Disclaimer from "@/components/Disclaimer";

const fadeUp = {
  hidden: { opacity: 0, y: 30 },
  visible: (i: number) => ({ opacity: 1, y: 0, transition: { delay: i * 0.1, duration: 0.5 } }),
};

const Index = () => {
  const { t } = useTranslation();

  const features = [
    { icon: Brain, title: t("landing.feature_ai"), desc: t("landing.feature_ai_desc") },
    { icon: Stethoscope, title: t("landing.feature_triage"), desc: t("landing.feature_triage_desc") },
    { icon: MessageCircle, title: t("landing.feature_chat"), desc: t("landing.feature_chat_desc") },
    { icon: Shield, title: t("landing.feature_privacy"), desc: t("landing.feature_privacy_desc") },
    { icon: Clock, title: t("landing.feature_fast"), desc: t("landing.feature_fast_desc") },
    { icon: Heart, title: t("landing.feature_specialist"), desc: t("landing.feature_specialist_desc") },
  ];

  return (
    <div className="flex flex-col">
      {/* Hero */}
      <section className="relative overflow-hidden py-20 md:py-32">
        <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-primary/5" />
        <div className="container relative text-center">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center">
              <Brain className="h-16 w-16 text-primary glow-text" />
            </div>
            <h1 className="font-display text-4xl font-extrabold tracking-tight md:text-6xl lg:text-7xl">
              {t("landing.hero_title").split(" ").map((word, i) => (
                <span key={i} className={word === "AI-Powered" || word === "Smart" || word === "Health" ? "text-primary glow-text" : ""}>
                  {word}{" "}
                </span>
              ))}
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground md:text-xl">
              {t("landing.hero_subtitle")}
            </p>
            <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
              <Button size="lg" className="text-base px-8 bg-primary hover:bg-primary/90" asChild>
                <Link to="/symptom-checker">{t("landing.start_chat")}</Link>
              </Button>
              <Button size="lg" variant="outline" className="text-base px-8 border-primary/30" asChild>
                <Link to="/about">{t("landing.learn_more")}</Link>
              </Button>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20">
        <div className="container">
          <div className="text-center mb-14">
            <h2 className="font-display text-3xl font-bold md:text-4xl">{t("landing.features_title")}</h2>
            <p className="mt-3 text-muted-foreground">{t("landing.features_subtitle")}</p>
          </div>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((f, i) => (
              <motion.div key={f.title} custom={i} initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeUp}>
                <div className="glass-card-glow h-full p-6 hover:border-primary/50 transition-colors">
                  <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-primary/20">
                    <f.icon className="h-6 w-6 text-primary" />
                  </div>
                  <h3 className="font-display text-lg font-semibold mb-2">{f.title}</h3>
                  <p className="text-sm text-muted-foreground">{f.desc}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20">
        <div className="container">
          <div className="mx-auto max-w-3xl glass-card-glow p-10 text-center">
            <h2 className="font-display text-3xl font-bold">{t("landing.cta_title")}</h2>
            <p className="mt-3 text-muted-foreground">{t("landing.cta_subtitle")}</p>
            <Button size="lg" className="mt-6 text-base px-8 bg-primary hover:bg-primary/90" asChild>
              <Link to="/auth?tab=signup">{t("landing.create_account")}</Link>
            </Button>
          </div>
        </div>
      </section>

      {/* Disclaimer */}
      <section className="pb-10">
        <div className="container max-w-3xl">
          <Disclaimer />
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-primary/20 py-8">
        <div className="container text-center text-sm text-muted-foreground">
          <p>© 2025 AI Smart Health Assistant — For educational purposes only. Not a medical tool.</p>
        </div>
      </footer>
    </div>
  );
};

export default Index;
