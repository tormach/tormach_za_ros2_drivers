#ifndef RVIZ_ZA6_IO_PANEL__IO_PANEL_HPP_
#define RVIZ_ZA6_IO_PANEL__IO_PANEL_HPP_

#include <rviz_common/panel.hpp>
#include <rviz_common/ros_integration/ros_node_abstraction_iface.hpp>
#include <std_msgs/msg/bool.hpp>
#include <rclcpp/qos.hpp>
#include <QGridLayout>
#include <QLabel>
#include <QPushButton>
#include <vector>

namespace rviz_za6_io_panel
{

class IOPanel : public rviz_common::Panel
{
  Q_OBJECT

public:
  explicit IOPanel(QWidget* parent = nullptr);
  virtual ~IOPanel();

  virtual void onInitialize();
  QString getName() const override;

protected:
  std::shared_ptr<rviz_common::ros_integration::RosNodeAbstractionIface>
      node_ptr_;
  std::vector<rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr> input_subs_;
  std::vector<rclcpp::Publisher<std_msgs::msg::Bool>::SharedPtr> output_pubs_;

  std::vector<QLabel*> input_labels_;
  std::vector<QPushButton*> output_buttons_;

  void inputCallback(int index, const std_msgs::msg::Bool::SharedPtr msg);

private Q_SLOTS:
  void outputButtonClicked(int index);
};

}  // namespace rviz_za6_io_panel

#endif  // RVIZ_ZA6_IO_PANEL__IO_PANEL_HPP_
