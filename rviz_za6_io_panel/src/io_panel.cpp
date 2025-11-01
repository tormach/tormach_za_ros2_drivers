#include "rviz_za6_io_panel/io_panel.hpp"
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QGroupBox>
#include <QTabWidget>
#include <QLabel>
#include <QPushButton>
#include <QGridLayout>
#include <rviz_common/display_context.hpp>
#include <sstream>
#include <iomanip>

namespace rviz_za6_io_panel
{

IOPanel::IOPanel(QWidget* parent) : rviz_common::Panel(parent)
{
  auto main_layout = new QVBoxLayout();

  // Create the tab widget
  auto tab_widget = new QTabWidget();

  // --- Digital Inputs Tab ---
  QWidget* inputs_tab = new QWidget();
  auto input_layout = new QGridLayout(inputs_tab);

  input_layout->setHorizontalSpacing(4);  // small spacing between label/state
                                          // columns
  input_layout->setVerticalSpacing(6);
  input_layout->setContentsMargins(2, 2, 2, 2);

  // Total columns per row = 3 * 4 (label + button + spacer)
  int pairs_per_row = 4;
  int total_cols = pairs_per_row * 3;

  for (int col = 0; col < total_cols; ++col)
  {
    input_layout->setColumnStretch(col, 0);
    if ((col + 1) % 3 == 0)
    {
      // Spacer column: set fixed minimum width for visual gap
      input_layout->setColumnMinimumWidth(col, 15);
    }
    else
    {
      input_layout->setColumnMinimumWidth(col, 0);
    }
  }

  for (int i = 1; i <= 16; ++i)
  {
    int pair_index = (i - 1) % pairs_per_row;
    int row = (i - 1) / pairs_per_row;
    int label_col = pair_index * 3;  // label column: 0, 3, 6, 9
    int state_col = label_col + 1;   // state column: 1, 4, 7, 10

    auto name_label = new QLabel(QString("DIN%1:").arg(i, 2, 10, QChar('0')));
    name_label->setMinimumWidth(45);
    name_label->setAlignment(Qt::AlignRight | Qt::AlignVCenter);

    auto state_label = new QLabel("--");
    state_label->setStyleSheet("QLabel { padding: 2px; background-color: #555; "
                               "color: white; "
                               "border-radius: 3px; min-width: 25px; "
                               "font-size: 10pt; }");
    state_label->setAlignment(Qt::AlignCenter);
    state_label->setMinimumSize(25, 16);
    state_label->setMaximumSize(30, 20);

    input_layout->addWidget(name_label, row, label_col);
    input_layout->addWidget(state_label, row, state_col);
    input_labels_.push_back(state_label);
  }

  tab_widget->addTab(inputs_tab, "Digital Inputs");

  // --- Digital Outputs Tab ---
  QWidget* outputs_tab = new QWidget();
  auto output_layout = new QGridLayout(outputs_tab);

  output_layout->setHorizontalSpacing(4);  // small spacing between label/button
                                           // pairs
  output_layout->setVerticalSpacing(6);
  output_layout->setContentsMargins(2, 2, 2, 2);

  for (int col = 0; col < total_cols; ++col)
  {
    output_layout->setColumnStretch(col, 0);
    if ((col + 1) % 3 == 0)
    {
      // Spacer column: set a fixed minimum width for the gap
      output_layout->setColumnMinimumWidth(col,
                                           15);  // adjust gap width as needed
    }
    else
    {
      output_layout->setColumnMinimumWidth(col, 0);
    }
  }

  for (int i = 1; i <= 16; ++i)
  {
    int pair_index = (i - 1) % pairs_per_row;
    int row = (i - 1) / pairs_per_row;
    int label_col = pair_index * 3;  // label in col 0,3,6,9...
    int button_col = label_col + 1;  // button in col 1,4,7,10...

    // Label for output number
    auto label = new QLabel(QString("DOUT%1:").arg(i, 2, 10, QChar('0')));
    label->setMinimumWidth(45);
    label->setAlignment(Qt::AlignRight | Qt::AlignVCenter);

    // On/Off toggle button, smaller size
    auto button = new QPushButton("OFF");
    button->setCheckable(true);
    button->setStyleSheet("QPushButton { padding: 1px 6px; min-width: 30px; "
                          "font-size: 9pt; }"
                          "QPushButton:checked { background-color: #00AA00; "
                          "color: white; }"
                          "QPushButton:!checked { background-color: #555555; "
                          "color: white; }");
    button->setMinimumSize(30, 18);
    button->setMaximumSize(40, 22);
    button->setSizePolicy(QSizePolicy::Fixed, QSizePolicy::Fixed);

    connect(button, &QPushButton::clicked,
            [this, i]() { outputButtonClicked(i); });

    output_layout->addWidget(label, row, label_col);
    output_layout->addWidget(button, row, button_col);

    output_buttons_.push_back(button);
  }

  tab_widget->addTab(outputs_tab, "Digital Outputs");

  // Add tab widget as main layout widget
  main_layout->addWidget(tab_widget);
  setLayout(main_layout);
}

IOPanel::~IOPanel()
{
}

QString rviz_za6_io_panel::IOPanel::getName() const
{
  return QString("Digital IO");
}

void IOPanel::onInitialize()
{
  auto ros_node_abstraction = getDisplayContext()->getRosNodeAbstraction();
  if (!ros_node_abstraction.lock())
  {
    return;
  }

  node_ptr_ = ros_node_abstraction.lock();
  auto node = node_ptr_->get_raw_node();

  // Create QoS profile with BEST_EFFORT reliability
  rclcpp::QoS qos_profile(10);
  qos_profile.reliability(rclcpp::ReliabilityPolicy::BestEffort);
  qos_profile.history(rclcpp::HistoryPolicy::KeepLast);

  // Subscribe to digital inputs
  for (int i = 1; i <= 16; i++)
  {
    std::stringstream ss;
    ss << "/din" << std::setfill('0') << std::setw(2) << i;
    std::string topic = ss.str();

    auto sub = node->create_subscription<std_msgs::msg::Bool>(
        topic, qos_profile,
        [this, i](const std_msgs::msg::Bool::SharedPtr msg) {
          inputCallback(i, msg);
        });
    input_subs_.push_back(sub);
  }

  // Create publishers for digital outputs
  for (int i = 1; i <= 16; i++)
  {
    std::stringstream ss;
    ss << "/hal_io/dout" << std::setfill('0') << std::setw(2) << i;
    std::string topic = ss.str();

    auto pub = node->create_publisher<std_msgs::msg::Bool>(topic, qos_profile);
    output_pubs_.push_back(pub);
  }
}

void IOPanel::inputCallback(int index, const std_msgs::msg::Bool::SharedPtr msg)
{
  int array_idx = index - 1;

  QString state_text = msg->data ? "ON" : "OFF";
  QString color = msg->data ? "#00FF00" : "#555555";

  input_labels_[array_idx]->setText(state_text);
  input_labels_[array_idx]->setStyleSheet(QString("QLabel { padding: 5px; "
                                                  "background-color: %1; "
                                                  "color: white; "
                                                  "border-radius: 3px; "
                                                  "min-width: 50px; "
                                                  "font-weight: bold; }")
                                              .arg(color));
}

void IOPanel::outputButtonClicked(int index)
{
  int array_idx = index - 1;
  bool state = output_buttons_[array_idx]->isChecked();

  auto msg = std_msgs::msg::Bool();
  msg.data = state;
  output_pubs_[array_idx]->publish(msg);

  QString state_text = state ? "ON" : "OFF";
  output_buttons_[array_idx]->setText(state_text);
}

}  // namespace rviz_za6_io_panel

#include <pluginlib/class_list_macros.hpp>
PLUGINLIB_EXPORT_CLASS(rviz_za6_io_panel::IOPanel, rviz_common::Panel)
